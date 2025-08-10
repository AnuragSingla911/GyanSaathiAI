# AI Tutor App MVP

An AI-powered tutoring application for 6th to 10th-grade students, providing personalized learning experiences in Math and Science using synthetic educational content generated from open-source educational resources.

## Features

- **User Authentication**: JWT-based login/signup with role-based access
- **Adaptive Learning**: AI-driven difficulty adjustment based on performance
- **Synthetic Content**: Dynamic question and explanation generation using fine-tuned GPT models
- **Quiz Management**: Dynamic quiz generation with real-time feedback
- **Progress Tracking**: Comprehensive analytics and performance visualization
- **Real-time Feedback**: AI-powered explanations and step-by-step solutions

## Architecture

### Frontend
- React.js with Material-UI
- Responsive design for web and mobile
- Real-time progress visualization

### Backend
- Node.js with Express
- PostgreSQL for user data
- MongoDB for generated content
- JWT authentication

### AI/ML Pipeline
- Fine-tuned GPT models for content generation
- FastAPI for model serving
- MLflow for experiment tracking

## Quick Start

```bash
# Clone and setup
npm install
docker-compose up -d

# Access the application
http://localhost:3000
```

## Development

### Prerequisites
- Node.js 18+
- Python 3.9+
- Docker & Docker Compose
- PostgreSQL
- MongoDB

### Setup
```bash
# Install dependencies
npm run install:all

# Start development environment
npm run dev

# Run tests
npm test
```

## Deployment

The application is containerized using Docker and can be deployed locally or to cloud platforms.

```bash
# Build and deploy
docker-compose up --build
```

## License

MIT License - Educational use focused on open-source educational resources.