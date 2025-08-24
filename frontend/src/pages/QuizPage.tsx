
import React, { useMemo, useState } from 'react';
import {
  Box, Container, Typography, Card, CardContent, Button, Chip, CircularProgress,
  Alert, RadioGroup, FormControlLabel, FormControl, FormLabel, Stack, Divider
} from '@mui/material';
import { Radio as MuiRadio } from '@mui/material';
import { Quiz, PlayArrow, Check } from '@mui/icons-material';
import { quizAPI } from '../services/api';

interface Question {
  _id: string;
  questionText: string;
  options: string[];
  correctAnswer: string;
  difficulty?: string;
  topic?: string;
}

interface QuizResult {
  questionId: string;
  question: string;
  userAnswer: string;
  correctAnswer: string;
  isCorrect: boolean;
}

const QuizPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [selectedAnswers, setSelectedAnswers] = useState<{ [key: string]: string }>({});
  const [submitted, setSubmitted] = useState(false);
  const [results, setResults] = useState<QuizResult[]>([]);

  const answeredCount = useMemo(
    () => Object.keys(selectedAnswers).length,
    [selectedAnswers]
  );

  const handleStartQuiz = async () => {
    setLoading(true);
    setError(null);
    try {
      const fetchedQuestions = await quizAPI.getQuestions({ limit: 5 });
      setQuestions(fetchedQuestions || []);
      setSelectedAnswers({});
      setSubmitted(false);
      setResults([]);
      // Smooth scroll to questions area
      setTimeout(() => document.getElementById('quiz-area')?.scrollIntoView({ behavior: 'smooth' }), 100);
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || 'Failed to fetch questions');
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerSelect = (questionId: string, answer: string) => {
    setSelectedAnswers(prev => ({ ...prev, [questionId]: answer }));
  };

  const handleSubmitQuiz = async () => {
    if (Object.keys(selectedAnswers).length < questions.length) {
      setError('Please answer all questions before submitting');
      // Scroll to first unanswered
      const firstUnanswered = questions.find((q: Question) => !selectedAnswers[q._id]);
      if (firstUnanswered) document.getElementById(`q-${firstUnanswered._id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    setLoading(true);
    try {
      const quizResults = questions.map((q: Question) => {
        const isCorrect = selectedAnswers[q._id] === q.correctAnswer;
        return {
          questionId: q._id,
          question: q.questionText,
          userAnswer: selectedAnswers[q._id],
          correctAnswer: q.correctAnswer,
          isCorrect
        };
      });
      setResults(quizResults);
      setSubmitted(true);
      setTimeout(() => window.scrollTo({ top: 0, behavior: 'smooth' }), 100);
    } catch (err: any) {
      setError(err?.response?.data?.message || err.message || 'Failed to submit quiz');
    } finally {
      setLoading(false);
    }
  };

  const resetQuiz = () => {
    setQuestions([]);
    setSelectedAnswers({});
    setSubmitted(false);
    setResults([]);
    setError(null);
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
              Get AI-generated questions, real-time feedback, and adaptive difficulty.
            </Typography>
            <Stack direction="row" spacing={1} justifyContent="center" mb={3} flexWrap="wrap">
              <Chip label="AI-Generated" color="primary" variant="outlined" />
              <Chip label="Adaptive Difficulty" color="secondary" variant="outlined" />
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

      {/* Questions */}
      {questions.length > 0 && !submitted && !loading && (
        <Box id="quiz-area">
          <Card elevation={0} sx={{ borderRadius: 3, border: '1px solid', borderColor: 'divider', mt: 2 }}>
            <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                <Typography variant="h5" fontWeight={700}>Quiz Questions</Typography>
                <Chip
                  label={`Answered ${answeredCount}/${questions.length}`}
                  color={answeredCount === questions.length ? 'success' : 'default'}
                  variant="outlined"
                />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Select one option per question and submit when ready.
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Stack spacing={2}>
                {questions.map((q: Question, idx: number) => {
                  const selected = selectedAnswers[q._id];
                  const unanswered = !selected && answeredCount > 0;
                  return (
                    <Card
                      id={`q-${q._id}`}
                      key={q._id}
                      variant="outlined"
                      sx={{
                        borderRadius: 2,
                        transition: 'box-shadow 0.2s, border-color 0.2s',
                        borderColor: unanswered ? 'warning.light' : 'divider',
                        '&:hover': { boxShadow: 2, borderColor: 'primary.light' }
                      }}
                    >
                      <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                        <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                          <Chip size="small" label={`Q${idx + 1}`} color="primary" variant="filled" />
                          {q.difficulty && (
                            <Chip
                              size="small"
                              label={q.difficulty}
                              color={q.difficulty === 'easy' ? 'success' : q.difficulty === 'hard' ? 'error' : 'warning'}
                              variant="outlined"
                            />
                          )}
                          {q.topic && <Chip size="small" label={q.topic} variant="outlined" />}
                        </Stack>

                        <Typography variant="h6" sx={{ mb: 1.5, fontWeight: 700 }}>
                          {q.questionText}
                        </Typography>

                        <FormControl component="fieldset" sx={{ width: '100%' }}>
                          <RadioGroup
                            value={selected || ''}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleAnswerSelect(q._id, e.target.value)}
                          >
                            {q.options && Array.isArray(q.options) && q.options.map((option: string, optionIdx: number) => (
                              <FormControlLabel
                                key={optionIdx}
                                value={option}
                                control={<MuiRadio color="primary" />}
                                label={option}
                                sx={{
                                  mx: 0,
                                  my: 0.5,
                                  p: 1,
                                  borderRadius: 1.5,
                                  border: '1px solid',
                                  borderColor: selected === option ? 'primary.main' : 'divider',
                                  backgroundColor: selected === option ? 'action.selected' : 'background.paper',
                                  transition: 'all 0.15s',
                                  '&:hover': {
                                    backgroundColor: 'action.hover',
                                  },
                                }}
                              />
                            ))}
                          </RadioGroup>
                        </FormControl>
                      </CardContent>
                    </Card>
                  );
                })}
              </Stack>
            </CardContent>
          </Card>

          {/* Sticky action bar */}
          <Box
            sx={{
              position: 'sticky',
              bottom: 0,
              mt: 2,
              py: 1.5,
              px: { xs: 2, sm: 3 },
              backgroundColor: 'background.paper',
              borderTop: '1px solid',
              borderColor: 'divider',
              boxShadow: 3,
              borderRadius: 2,
            }}
          >
            <Stack direction={{ xs: 'column', sm: 'row' }} alignItems="center" justifyContent="space-between" spacing={1}>
              <Typography variant="body2" color="text.secondary">
                {answeredCount < questions.length
                  ? `Answer all questions to enable submission (${answeredCount}/${questions.length})`
                  : 'All questions answered. Ready to submit.'}
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button variant="text" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
                  Back to Top
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  onClick={handleSubmitQuiz}
                  disabled={answeredCount < questions.length || loading}
                >
                  Submit Quiz
                </Button>
              </Stack>
            </Stack>
          </Box>
        </Box>
      )}

      {/* Results */}
      {submitted && results.length > 0 && (
        <Card elevation={0} sx={{ borderRadius: 3, border: '1px solid', borderColor: 'divider', mt: 2 }}>
          <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
              <Check color="success" />
              <Typography variant="h5" fontWeight={700}>Quiz Results</Typography>
            </Stack>
            <Stack spacing={2}>
              {results.map((r: QuizResult, idx: number) => (
                <Card
                  key={idx}
                  variant="outlined"
                  sx={{
                    borderRadius: 2,
                    borderColor: r.isCorrect ? 'success.light' : 'error.light',
                    backgroundColor: r.isCorrect ? 'success.lighter' : 'error.lighter'
                  }}
                >
                  <CardContent sx={{ p: { xs: 2, sm: 3 } }}>
                    <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                      Q{idx + 1}: {r.question}
                    </Typography>
                    <Typography color={r.isCorrect ? 'success.main' : 'error.main'}>
                      Your Answer: {r.userAnswer}
                    </Typography>
                    <Typography color="text.secondary">
                      Correct Answer: {r.correctAnswer}
                    </Typography>
                    <Typography
                      color={r.isCorrect ? 'success.main' : 'error.main'}
                      sx={{ mt: 1, fontWeight: 700 }}
                    >
                      {r.isCorrect ? '✓ Correct!' : '✗ Incorrect'}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Stack>

            <Divider sx={{ my: 2 }} />

            <Stack alignItems="center" spacing={2}>
              <Typography variant="h6" fontWeight={800}>
                Score: {results.filter((r: QuizResult) => r.isCorrect).length}/{results.length} (
                {Math.round((results.filter((r: QuizResult) => r.isCorrect).length / results.length) * 100)}%)
              </Typography>
              <Button variant="contained" size="large" onClick={resetQuiz}>
                Take Another Quiz
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}
    </Container>
  );
};

export default QuizPage;