const { query, transaction } = require('../utils/database');
const redis = require('../utils/redis');
const { v4: uuidv4 } = require('uuid');

// Use the existing model but we'll map the fields correctly
const VersionedQuestion = require('../models/question');

class QuizService {
  // Test MongoDB connection
  async testMongoConnection() {
    try {
      console.log('QuizService: Testing MongoDB connection...');
      const count = await VersionedQuestion.countDocuments();
      console.log('QuizService: MongoDB connection successful, total questions:', count);
      return true;
    } catch (error) {
      console.error('QuizService: MongoDB connection failed:', error);
      return false;
    }
  }

  // Start a new quiz attempt
  async startQuizAttempt(userId, { subject, topic, totalQuestions, skillFilters }) {
    try {
      console.log('QuizService: Starting quiz attempt for user:', userId);
      console.log('QuizService: Input params:', { subject, topic, totalQuestions, skillFilters });
      
      // Build question filter - try to match your actual MongoDB data
      const questionFilter = { status: 'active' };

      // Subject filter (case-insensitive) with simple synonym/alias handling
      if (subject && subject.trim()) {
        const s = subject.trim().toLowerCase();
        let pattern = subject.trim();
        if (s.includes('math')) {
          pattern = '(math|mathematics|maths)';
        } else if (s.includes('phys')) {
          pattern = '(phys|physics)';
        } else if (s.includes('chem')) {
          pattern = '(chem|chemistry)';
        } else if (s.includes('bio')) {
          pattern = '(bio|biology|life sciences)';
        } else if (s.includes('sci')) {
          pattern = '(sci|science)';
        }
        questionFilter.subject = { $regex: new RegExp(pattern, 'i') };
      }

      // Topic filter (case-insensitive)
      if (topic && topic.trim()) {
        questionFilter.topic = { $regex: new RegExp(topic.trim(), 'i') };
      }
      
      
      console.log('QuizService: Base question filter (subject/topic):', questionFilter);
      
      // Prefer ACTIVE first, then fill with DRAFT if needed (to support freshly generated items)
      console.log('QuizService: Querying MongoDB for ACTIVE questions...');
      const activeQuestions = await VersionedQuestion.find({ ...questionFilter, status: 'active' }).lean();
      let availableQuestions = [...activeQuestions];
      
      if (availableQuestions.length < (totalQuestions || 0)) {
        console.log('QuizService: Not enough ACTIVE questions, querying DRAFT to top-up...');
        const draftQuestions = await VersionedQuestion.find({ ...questionFilter, status: 'draft' }).lean();
        // Deduplicate by _id
        const existingIds = new Set(availableQuestions.map(q => String(q._id)));
        for (const q of draftQuestions) {
          if (!existingIds.has(String(q._id))) availableQuestions.push(q);
        }
      }
      console.log('QuizService: Total available (active+draft) with filters:', availableQuestions.length);
      
      // If none found and a topic was requested, do NOT fallback to other topics
      if (availableQuestions.length === 0 && topic && topic.trim()) {
        console.log('QuizService: No questions found for exact subject+topic. Aborting without unrelated fallback.');
        throw new Error('No questions available for the specified subject and topic');
      }

      // If none with both filters, relax to subject-only (only when topic not specified)
      if (availableQuestions.length === 0 && subject && (!topic || !topic.trim())) {
        console.log('QuizService: No questions found with subject+topic, trying subject-only...');
        const s = subject.trim().toLowerCase();
        let pattern = subject.trim();
        if (s.includes('math')) {
          pattern = '(math|mathematics|maths)';
        } else if (s.includes('phys')) {
          pattern = '(phys|physics)';
        } else if (s.includes('chem')) {
          pattern = '(chem|chemistry)';
        } else if (s.includes('bio')) {
          pattern = '(bio|biology|life sciences)';
        } else if (s.includes('sci')) {
          pattern = '(sci|science)';
        }
        const subjectOnly = await VersionedQuestion.find({ status: 'active', subject: { $regex: new RegExp(pattern, 'i') } }).limit(totalQuestions * 2).lean();
        if (subjectOnly.length > 0) availableQuestions.push(...subjectOnly);
      }
      
      // If still no questions, try to find ANY active questions
      if (availableQuestions.length === 0) {
        console.log('QuizService: No questions found with any filter, trying to find any active questions...');
        const anyQuestions = await VersionedQuestion.find({ status: 'active' }).limit(5).lean();
        console.log('QuizService: Found any active questions:', anyQuestions.length);
        if (anyQuestions.length > 0) {
          availableQuestions.push(...anyQuestions);
        }
      }
      
      
      console.log('QuizService: Total available questions:', availableQuestions.length);
      
      // Randomly select questions
      const selectedQuestions = availableQuestions
        .sort(() => 0.5 - Math.random())
        .slice(0, totalQuestions);

      console.log('QuizService: Selected questions:', selectedQuestions.length);

      if (selectedQuestions.length === 0) {
        throw new Error('No questions available for the specified criteria');
      }

      // Create quiz attempt in transaction
      console.log('QuizService: Starting PostgreSQL transaction...');
      const result = await transaction(async (client) => {
        console.log('QuizService: Creating quiz attempt...');
        // Create quiz attempt
        const attemptResult = await client.query(
          `INSERT INTO quizzes (user_id, subject, topic, total_questions, difficulty_level, time_taken, status, started_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           RETURNING quiz_id, started_at`,
          [userId, subject, topic, totalQuestions, 'medium', 0, 'in_progress', new Date()]
        );

        const attempt = attemptResult.rows[0];
        console.log('QuizService: Created quiz attempt:', attempt.quiz_id);

        // Create attempt items with question snapshots
        console.log('QuizService: Creating quiz responses...');
        for (let i = 0; i < selectedQuestions.length; i++) {
          const question = selectedQuestions[i];
          console.log('QuizService: Question:', question);
          await client.query(
            `INSERT INTO quiz_responses (quiz_id, user_id, question_id, user_answer, correct_answer, is_correct, time_spent, difficulty_level, hints_used, attempts)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
            [attempt.quiz_id, userId, question._id.toString(), null, question.correctAnswer || question.content?.canonicalSolution || question.content?.correctOptionIds?.[0], null, 0, question.difficulty || 'medium', 0, 1]
          );
        }

        console.log('QuizService: Created all quiz responses');
        return attempt;
      });

      console.log('QuizService: Transaction completed successfully');
      
      console.log('QuizService: About to return result...');
      const returnData = {
        attemptId: result.quiz_id,
        subject: subject, // Use input parameter
        topic: topic, // Use input parameter
        totalQuestions: totalQuestions, // Use input parameter
        timeLimitSeconds: null,
        startedAt: result.started_at,
        questions: selectedQuestions
      };
      console.log('QuizService: Result object created:', returnData);
      
      return returnData;
    } catch (error) {
      console.error('QuizService: Error starting quiz attempt:', error);
      throw error;
    }
  }

  // Get quiz attempt details
  async getQuizAttempt(attemptId, userId) {
    try {
      console.log('QuizService: Getting quiz attempt:', attemptId, 'for user:', userId);
      
      // Get quiz attempt from PostgreSQL
      const attemptResult = await query(
        `SELECT q.*, 
                COUNT(qr.response_id) as total_questions,
                COUNT(CASE WHEN qr.user_answer IS NOT NULL THEN 1 END) as answered_questions
         FROM quizzes q
         LEFT JOIN quiz_responses qr ON q.quiz_id = qr.quiz_id
         WHERE q.quiz_id = $1 AND q.user_id = $2
         GROUP BY q.quiz_id`,
        [attemptId, userId]
      );

      if (attemptResult.rows.length === 0) {
        throw new Error('Quiz attempt not found');
      }

      const attempt = attemptResult.rows[0];
      console.log('QuizService: Found quiz attempt:', attempt);

      // Get quiz responses
      const responsesResult = await query(
        `SELECT qr.*
         FROM quiz_responses qr
         WHERE qr.quiz_id = $1
         ORDER BY qr.response_id`,
        [attemptId]
      );

      console.log('QuizService: Found responses:', responsesResult.rows.length);

      // Fetch questions from MongoDB for each response
      const items = [];
      for (const row of responsesResult.rows) {
        try {
          // Convert string question_id back to ObjectId for MongoDB query
          const { ObjectId } = require('mongodb');
          const questionId = new ObjectId(row.question_id);
          
          // Get question from MongoDB
          const question = await VersionedQuestion.findById(questionId).lean();
          
          if (question) {
            // Debug logging for options transformation
            console.log('QuizService: Processing question ID:', question._id.toString());
            console.log('QuizService: Question stem:', question.questionText || question.content?.stem);
            console.log('QuizService: Original MongoDB options:', question.options);
            console.log('QuizService: Original MongoDB correctAnswer:', question.correctAnswer);
            
            const transformedOptions = question.options ? question.options.map((opt, index) => ({
              id: String.fromCharCode(97 + index), // 'a', 'b', 'c', 'd'
              text: opt
            })) : question.content?.options || [];
            
            console.log('QuizService: Transformed options for question', question._id.toString(), ':', transformedOptions);
            
            const correctOptionId = question.correctAnswer ? 
              String.fromCharCode(97 + question.options.indexOf(question.correctAnswer)) : 
              null;
            
            console.log('QuizService: Calculated correctOptionId for question', question._id.toString(), ':', correctOptionId);
            
            items.push({
              item_id: row.response_id,
              question: {
                id: question._id.toString(),
                version: 1,
                status: 'active',
                stem: question.questionText || question.content?.stem || 'Question',
                options: transformedOptions,
                correctOptionIds: correctOptionId ? [correctOptionId] : question.content?.correctOptionIds || [],
                canonicalSolution: question.correctAnswer || question.content?.canonicalSolution || 'Solution not available',
                unit: question.content?.unit || null,
                tags: question.tags || [],
                subject: question.subject,
                topic: question.topic,
                difficulty: question.difficulty
              },
              shown_payload: null,
              userAnswer: row.user_answer,
              isCorrect: row.is_correct,
              score: row.is_correct ? 1.0 : 0.0, // Calculate score locally
              timeSpent: row.time_spent || 0,
              hintsUsed: row.hints_used || 0,
              answeredAt: row.created_at // Use created_at instead of answered_at
            });
          } else {
            console.log('QuizService: Question not found in MongoDB:', row.question_id);
          }
        } catch (questionError) {
          console.error('QuizService: Error fetching question from MongoDB:', questionError);
        }
      }

      console.log('QuizService: Processed items:', items.length);

      return {
        attempt_id: attempt.quiz_id,
        user_id: attempt.user_id,
        subject: attempt.subject,
        topic: attempt.topic,
        totalQuestions: attempt.total_questions,
        timeLimitSeconds: null,
        startedAt: attempt.started_at,
        completedAt: attempt.completed_at,
        finalScore: attempt.score,
        answeredQuestions: attempt.answered_questions,
        status: attempt.status,
        items
      };
    } catch (error) {
      console.error('QuizService: Error getting quiz attempt:', error);
      throw error;
    }
  }

  // Save answer
  async saveAnswer(attemptId, itemId, userId, { answer, timeSpent, hintsUsed }) {
    try {
      console.log('QuizService: Saving answer for item:', itemId, 'in attempt:', attemptId);
      
      // Get the quiz response
      const responseResult = await query(
        `SELECT qr.*
         FROM quiz_responses qr
         WHERE qr.response_id = $1 AND qr.quiz_id = $2 AND qr.user_id = $3`,
        [itemId, attemptId, userId]
      );

      if (responseResult.rows.length === 0) {
        throw new Error('Quiz response not found');
      }

      const response = responseResult.rows[0];
      
      // Get question from MongoDB to check correctness
      const question = await VersionedQuestion.findById(response.question_id).lean();
      
      if (!question) {
        throw new Error('Question not found');
      }
      
      console.log('QuizService: Question found:', question.questionText || question.content?.stem);
      console.log('QuizService: User answer:', answer);
      console.log('QuizService: Correct answer:', question.correctAnswer || question.content?.canonicalSolution);
      
      // Check if answer is correct
      const isCorrect = question.correctAnswer === answer || question.content?.correctOptionIds?.includes(answer) || false;
      const score = isCorrect ? 1.0 : 0.0;

      console.log('QuizService: Answer is correct:', isCorrect);

      // Update the response
      await query(
        `UPDATE quiz_responses 
         SET user_answer = $1, is_correct = $2, time_spent = $3, hints_used = $4
         WHERE response_id = $5`,
        [answer, isCorrect, timeSpent || 0, hintsUsed || 0, itemId]
      );

      console.log('QuizService: Answer saved successfully');

      return {
        isCorrect,
        score: isCorrect ? 1.0 : 0.0, // Calculate score locally since column doesn't exist
        correctAnswer: question.correctAnswer || question.content?.canonicalSolution
      };
    } catch (error) {
      console.error('QuizService: Error saving answer:', error);
      throw error;
    }
  }

  // Submit quiz attempt
  async submitQuizAttempt(attemptId, userId) {
    try {
      // Get quiz attempt
      const attemptResult = await query(
        `SELECT * FROM quizzes WHERE quiz_id = $1 AND user_id = $2`,
        [attemptId, userId]
      );

      if (attemptResult.rows.length === 0) {
        throw new Error('Quiz attempt not found');
      }

      // Calculate final score
      const scoreResult = await query(
        `SELECT 
           COUNT(*) as total_questions,
           COUNT(CASE WHEN is_correct = true THEN 1 END) as correct_answers
         FROM quiz_responses 
         WHERE quiz_id = $1`,
        [attemptId]
      );

      const stats = scoreResult.rows[0];
      const finalScore = stats.correct_answers > 0 ? (stats.correct_answers / stats.total_questions) * 100 : 0;
      const answeredQuestions = stats.correct_answers || 0;

      // Update quiz attempt with final score
      await query(
        `UPDATE quizzes 
         SET status = 'completed', completed_at = $1, score = $2
         WHERE quiz_id = $3`,
        [new Date(), finalScore, attemptId]
      );

      // Publish progress event
      // await publishProgressEvent({ // This line was removed as per the new_code
      //   type: 'quiz_completed',
      //   userId,
      //   quizId: attemptId,
      //   score: finalScore,
      //   totalQuestions: stats.total_questions
      // });

      return {
        finalScore,
        answeredQuestions,
        totalQuestions: stats.total_questions
      };
    } catch (error) {
      console.error('QuizService: Error submitting quiz attempt:', error);
      throw error;
    }
  }
}

module.exports = new QuizService();
