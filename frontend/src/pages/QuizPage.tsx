
import React, { useState, useEffect } from 'react';
import { useQuery } from '@apollo/client';
import {
  Container,
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Alert,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio as MuiRadio,
  Chip,
  Stack,
  Divider,
  CircularProgress,
  LinearProgress,
} from '@mui/material';
import {
  Quiz,
  PlayArrow,
  Check,
  Timer,
} from '@mui/icons-material';
import { useQuizAPI } from '../services/graphqlApi';
import { GET_QUIZ_ATTEMPT } from '../graphql/operations';

interface Question {
  questionId: string;
  question: {
    stem: string;
    options: Array<{ id: string; text: string }>;
  };
  metadata: {
    subject: string;
    topic: string;
    tags: string[];
  };
}

interface QuizAttempt {
  attemptId: string;
  subject: string;
  topic?: string;
  totalQuestions: number;
  startedAt: string;
}

const QuizPage: React.FC = () => {
  const { startQuizAttempt, saveAnswer, submitQuizAttempt } = useQuizAPI();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentAttempt, setCurrentAttempt] = useState<QuizAttempt | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<{ [key: string]: string }>({});
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [timeSpent, setTimeSpent] = useState<{ [key: string]: number }>({});
  const [startTime, setStartTime] = useState<Date | null>(null);
  
  // GraphQL query for quiz attempt details
  const { data: attemptDetails, error: attemptError } = useQuery(GET_QUIZ_ATTEMPT, {
    variables: { attemptId: currentAttempt?.attemptId || '' },
    skip: !currentAttempt?.attemptId,
    fetchPolicy: 'no-cache', // Disable caching to prevent reference sharing issues
    errorPolicy: 'all'
  });
  
  const currentQuestion = questions[currentQuestionIndex];
  const answeredCount = Object.keys(selectedAnswers).length;
  const progress = (answeredCount / questions.length) * 100;

  // Effect to handle quiz attempt data changes
  useEffect(() => {
    if (attemptDetails?.quizAttempt?.items) {
      console.log('QuizPage: Raw GraphQL response received:', attemptDetails);
      
      // Debug: Log the raw data before any processing
      console.log('QuizPage: Raw items before mapping:', attemptDetails.quizAttempt.items);
      
      // Debug: Check each item's options before any processing
      attemptDetails.quizAttempt.items.forEach((item: any, index: number) => {
        console.log(`QuizPage: Raw item ${index} options:`, {
          item_id: item.item_id,
          questionId: item.question?.id,
          stem: item.question?.stem,
          rawOptions: item.question?.options,
          optionsLength: item.question?.options?.length,
          firstOption: item.question?.options?.[0],
          lastOption: item.question?.options?.[item.question?.options?.length - 1]
        });
      });
      
      console.log('QuizPage: Attempt details structure:', {
        hasAttempt: !!attemptDetails?.quizAttempt,
        hasItems: !!attemptDetails?.quizAttempt?.items,
        itemsLength: attemptDetails?.quizAttempt?.items?.length,
        firstItem: attemptDetails?.quizAttempt?.items?.[0],
        firstItemQuestion: attemptDetails?.quizAttempt?.items?.[0]?.question
      });
      
      // Debug: Log each item individually
      attemptDetails.quizAttempt.items.forEach((item: any, index: number) => {
        console.log(`QuizPage: Item ${index}:`, {
          item_id: item.item_id,
          questionId: item.question?.id,
          stem: item.question?.stem,
          options: item.question?.options,
          optionsLength: item.question?.options?.length,
          firstOption: item.question?.options?.[0],
          lastOption: item.question?.options?.[item.question?.options?.length - 1]
        });
      });
      
      const mappedQuestions = attemptDetails.quizAttempt.items.map((item: any, index: number) => {
        // Create a deep copy of the question to avoid reference sharing issues
        const questionCopy = {
          ...item.question,
          options: item.question.options ? [...item.question.options.map((opt: any) => ({ ...opt }))] : [],
          correctOptionIds: item.question.correctOptionIds ? [...item.question.correctOptionIds] : []
        };
        
        const mappedQuestion = {
          questionId: item.item_id,
          question: questionCopy,
          metadata: item.question.metadata || {
            subject: item.question.subject,
            topic: item.question.topic,
            tags: item.question.tags
          }
        };
        
        console.log(`QuizPage: Mapped question ${index}:`, {
          questionId: mappedQuestion.questionId,
          stem: mappedQuestion.question?.stem,
          options: mappedQuestion.question?.options,
          optionsLength: mappedQuestion.question?.options?.length,
          firstOption: mappedQuestion.question?.options?.[0],
          lastOption: mappedQuestion.question?.options?.[mappedQuestion.question?.options?.length - 1]
        });
        
        return mappedQuestion;
      });
      
      console.log('QuizPage: All mapped questions:', mappedQuestions);
      setQuestions(mappedQuestions);
    }
  }, [attemptDetails]);

  // Debug effect for current question changes
  useEffect(() => {
    if (currentQuestion) {
      console.log('QuizPage: Current question changed:', {
        questionIndex: currentQuestionIndex,
        questionId: currentQuestion?.questionId,
        stem: currentQuestion?.question?.stem,
        options: currentQuestion?.question?.options,
        optionsLength: currentQuestion?.question?.options?.length
      });
    }
  }, [currentQuestion, currentQuestionIndex]);

  // Handle attempt errors
  useEffect(() => {
    if (attemptError) {
      console.error('QuizPage: Attempt error:', attemptError);
      setError(attemptError.message || 'Failed to load quiz attempt');
    }
  }, [attemptError]);

  // Timer effect
  useEffect(() => {
    if (startTime && currentQuestion) {
      const timer = setInterval(() => {
        const questionId = currentQuestion.questionId;
        setTimeSpent(prev => ({
          ...prev,
          [questionId]: Math.floor((Date.now() - startTime.getTime()) / 1000)
        }));
      }, 1000);

      return () => clearInterval(timer);
    }
  }, [startTime, currentQuestion]);

  const handleStartQuiz = async () => {
    console.log('QuizPage: Starting quiz...');
    setLoading(true);
    setError(null);
    try {
      // Start a new quiz attempt
      console.log('QuizPage: Calling startQuizAttempt...');
      const attempt = await startQuizAttempt({
        subject: 'Mathematics', // Match the MongoDB question subject
        topic: 'linear equations', // Match the MongoDB question topic
        totalQuestions: 5
      });
      console.log('QuizPage: Quiz attempt created:', attempt);

      setCurrentAttempt(attempt);
      
      // The useQuery hook will automatically fetch the data when currentAttempt changes
      // No need to manually refetch or add delays
      
      setSelectedAnswers({});
      setSubmitted(false);
      setResults([]);
      setCurrentQuestionIndex(0);
      setTimeSpent({});
      setStartTime(new Date());
      
      // Smooth scroll to questions area
      setTimeout(() => document.getElementById('quiz-area')?.scrollIntoView({ behavior: 'smooth' }), 100);
    } catch (err: any) {
      console.error('QuizPage: Error starting quiz:', err);
      setError(err?.response?.data?.message || err.message || 'Failed to start quiz');
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerSelect = (questionId: string, answer: string) => {
    setSelectedAnswers(prev => ({ ...prev, [questionId]: answer }));
  };

  const handleNextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1);
      setStartTime(new Date());
    }
  };

  const handlePreviousQuestion = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1);
      setStartTime(new Date());
    }
  };

  const handleSubmitQuiz = async () => {
    console.log('QuizPage: handleSubmitQuiz called');
    if (!currentAttempt) {
      console.log('QuizPage: No current attempt');
      return;
    }
    
    if (Object.keys(selectedAnswers).length < questions.length) {
      setError('Please answer all questions before submitting');
      return;
    }

    console.log('QuizPage: Starting quiz submission...');
    setLoading(true);
    try {
      // Submit all answers to the backend
      console.log('QuizPage: Submitting answers...');
      const answerPromises = questions.map(async (question, index) => {
        console.log(`QuizPage: Processing question ${index + 1}:`, question);
        const itemId = question.questionId;
        const answer = selectedAnswers[itemId];
        const questionTimeSpent = timeSpent[itemId] || 0;
        
        console.log(`QuizPage: Saving answer for item ${itemId}:`, { answer, timeSpent: questionTimeSpent });
        
        // Save each answer individually
        const result = await saveAnswer(
          currentAttempt.attemptId,
          itemId,
          {
            answer,
            timeSpent: questionTimeSpent,
            hintsUsed: 0 // Could be tracked if hints are implemented
          }
        );
        
        console.log(`QuizPage: Answer saved for item ${itemId}:`, result);
        
        return {
          questionId: itemId,
          question: question.question.stem,
          userAnswer: answer,
          isCorrect: result.isCorrect,
          score: result.score,
          timeSpent: questionTimeSpent
        };
      });

      console.log('QuizPage: Waiting for all answers to be saved...');
      const quizResults = await Promise.all(answerPromises);
      console.log('QuizPage: All answers saved:', quizResults);
      
      // Submit the completed attempt
      console.log('QuizPage: Submitting completed attempt...');
      const finalResult = await submitQuizAttempt(currentAttempt.attemptId);
      console.log('QuizPage: Attempt submitted:', finalResult);
      
      setResults(quizResults);
      setSubmitted(true);
      
      // Note: Dashboard refresh removed to avoid circular dependency
      // Progress will be updated when user returns to dashboard
      
      setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 100);
    } catch (err: any) {
      console.error('QuizPage: Error in handleSubmitQuiz:', err);
      setError(err?.response?.data?.message || err.message || 'Failed to submit quiz');
    } finally {
      setLoading(false);
    }
  };

  const resetQuiz = () => {
    setCurrentAttempt(null);
    setQuestions([]);
    setSelectedAnswers({});
    setSubmitted(false);
    setResults([]);
    setError(null);
    setCurrentQuestionIndex(0);
    setTimeSpent({});
    setStartTime(null);
  };

  return (
    <Container maxWidth="md" sx={{ pb: 10 }}>
      {/* Header */}
      <Box display="flex" alignItems="center" gap={2} mt={3} mb={2}>
        <Quiz color="primary" />
        <Typography variant="h4" fontWeight={800} letterSpacing={0.2}>
          Take a Quiz
        </Typography>
      </Box>

      {/* Intro / Loader / Errors */}
      {error && (
        <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>
      )}

      {questions.length === 0 && !submitted && !loading && (
        <Card elevation={2} sx={{ borderRadius: 3, overflow: 'hidden' }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <Quiz sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
            <Typography variant="h5" fontWeight={700} gutterBottom>
              Start a Quiz!
            </Typography>
            <Typography variant="body1" color="text.secondary" paragraph>
              Get AI-generated questions, real-time feedback, and track your progress.
            </Typography>
            <Stack direction="row" spacing={1} justifyContent="center" mb={3} flexWrap="wrap">
              <Chip label="AI-Generated" color="primary" variant="outlined" />
              <Chip label="Progress Tracking" color="secondary" variant="outlined" />
              <Chip label="Instant Feedback" color="success" variant="outlined" />
            </Stack>
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              size="large"
              onClick={handleStartQuiz}
            >
              Start Quiz
            </Button>
          </CardContent>
        </Card>
      )}

      {loading && (
        <Card elevation={1} sx={{ borderRadius: 3, mt: 2 }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <CircularProgress sx={{ mb: 2 }} />
            <Typography>Loading questions...</Typography>
          </CardContent>
        </Card>
      )}

      {/* Quiz Progress */}
      {questions.length > 0 && !submitted && !loading && (
        <Box id="quiz-area">
          <Card elevation={0} sx={{ borderRadius: 3, border: '1px solid', borderColor: 'divider', mb: 2 }}>
            <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                <Typography variant="h6" fontWeight={600}>
                  Question {currentQuestionIndex + 1} of {questions.length}
                </Typography>
                <Chip 
                  icon={<Timer />} 
                  label={`${timeSpent[currentQuestion?.questionId] || 0}s`}
                  variant="outlined"
                />
              </Box>
               
              <LinearProgress 
                variant="determinate" 
                value={progress} 
                sx={{ height: 8, borderRadius: 4, mb: 2 }}
              />
               
              <Typography variant="body2" color="text.secondary">
                {answeredCount} of {questions.length} questions answered
              </Typography>
            </CardContent>
          </Card>
        </Box>
      )}

      {/* Current Question */}
      {currentQuestion && !submitted && !loading && (
        <Card elevation={2} sx={{ borderRadius: 3, mb: 2 }}>
          <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
            <Box mb={3}>
              <Typography variant="h5" fontWeight={700} gutterBottom>
                Question {currentQuestionIndex + 1} of {questions.length}
              </Typography>
            
            <Typography variant="body1" paragraph>
              {currentQuestion?.question?.stem || 'Question not available'}
            </Typography>
               
              <FormControl component="fieldset" fullWidth>
                <FormLabel component="legend">Select your answer:</FormLabel>
                <RadioGroup
                  value={selectedAnswers[currentQuestion?.questionId] || ''}
                  onChange={(e) => handleAnswerSelect(currentQuestion?.questionId, e.target.value)}
                >
                  {currentQuestion?.question?.options?.map((option) => (
                    <FormControlLabel
                      key={`${currentQuestion?.questionId}-${option.id}`}
                      value={option.text}
                      control={<MuiRadio />}
                      label={option.text}
                      sx={{ 
                        border: '1px solid',
                        borderColor: selectedAnswers[currentQuestion?.questionId] === option.text 
                          ? 'primary.main' 
                          : 'divider',
                        borderRadius: 2,
                        px: 2,
                        py: 1,
                        mb: 1,
                        '&:hover': {
                          borderColor: 'primary.main',
                          bgcolor: 'action.hover'
                        }
                      }}
                    />
                  )) || <Typography>No options available</Typography>}
                </RadioGroup>
              </FormControl>
            </Box>

            {/* Navigation */}
            <Box display="flex" justifyContent="space-between">
              <Button
                variant="outlined"
                onClick={handlePreviousQuestion}
                disabled={currentQuestionIndex === 0}
              >
                Previous
              </Button>
               
              {currentQuestionIndex === questions.length - 1 ? (
                <Button
                  variant="contained"
                  onClick={handleSubmitQuiz}
                  disabled={Object.keys(selectedAnswers).length < questions.length}
                  startIcon={<Check />}
                >
                  Submit Quiz
                </Button>
              ) : (
                <Button
                  variant="contained"
                  onClick={handleNextQuestion}
                  disabled={!selectedAnswers[currentQuestion.questionId]}
                >
                  Next Question
                </Button>
              )}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {submitted && results.length > 0 && (
        <Card elevation={2} sx={{ borderRadius: 3, mt: 2 }}>
          <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
            <Box display="flex" alignItems="center" gap={2} mb={3}>
              <Check color="success" />
              <Typography variant="h5" fontWeight={700}>
                Quiz Completed!
              </Typography>
            </Box>
            
            <Typography variant="body1" color="text.secondary" paragraph>
              Your answers have been saved and progress has been updated. Check your dashboard to see your improvement!
            </Typography>

            <Divider sx={{ my: 2 }} />
            
            <Typography variant="h6" gutterBottom>Results Summary:</Typography>
            <Stack spacing={2}>
              {results.map((result, index) => (
                <Box
                  key={index}
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  p={2}
                  bgcolor="background.default"
                  borderRadius={2}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight="bold">
                      Question {index + 1}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Time: {result.timeSpent}s
                    </Typography>
                  </Box>
                  <Chip
                    label={result.isCorrect ? 'Correct' : 'Incorrect'}
                    color={result.isCorrect ? 'success' : 'error'}
                    size="small"
                  />
                </Box>
              ))}
            </Stack>

            <Box display="flex" justifyContent="center" mt={3}>
              <Button
                variant="contained"
                onClick={resetQuiz}
                startIcon={<PlayArrow />}
              >
                Take Another Quiz
              </Button>
            </Box>
          </CardContent>
        </Card>
      )}
    </Container>
  );
};

export default QuizPage;