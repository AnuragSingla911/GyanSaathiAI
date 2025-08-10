# AI Tutor App - Development Guide

## 🚀 Quick Start

### Prerequisites
- **Node.js** 18+ 
- **Python** 3.9+
- **Docker** & **Docker Compose**
- **Git**

### One-Command Setup
```bash
make start
```

This will:
1. Build all Docker images
2. Start all services (PostgreSQL, MongoDB, Redis, Backend, ML Service, Frontend)
3. Initialize databases
4. Make the app available at http://localhost:3000

### Manual Setup

1. **Clone and Install**
   ```bash
   git clone <repository-url>
   cd tutor
   make install
   ```

2. **Start Databases**
   ```bash
   make db-setup
   ```

3. **Start Development Servers**
   ```bash
   make dev
   ```

## 🏗️ Architecture Overview

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  Node.js Backend │    │   ML Service    │
│     (Port 3000)  │◄──►│    (Port 5000)   │◄──►│   (Port 8001)   │
│                 │    │                 │    │    (FastAPI)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │     Redis       │              │
         │              │   (Port 6379)   │              │
         │              └─────────────────┘              │
         │                                               │
         └─────────────┬─────────────────┬───────────────┘
                       │                 │
              ┌─────────────────┐ ┌─────────────────┐
              │   PostgreSQL    │ │    MongoDB      │
              │   (Port 5432)   │ │  (Port 27017)   │
              │   User Data     │ │Generated Content│
              └─────────────────┘ └─────────────────┘
```

### Technology Stack

**Frontend:**
- React 18 with TypeScript
- Material-UI v5 for components
- React Router for navigation
- React Query for data fetching
- Formik & Yup for forms
- Framer Motion for animations

**Backend:**
- Node.js with Express
- PostgreSQL for user data
- MongoDB for generated content
- Redis for caching
- JWT authentication
- Rate limiting & security middleware

**ML Service:**
- FastAPI with Python
- Transformers library for AI models
- MLflow for experiment tracking
- Template-based generation (with AI enhancement)

**DevOps:**
- Docker & Docker Compose
- GitHub Actions CI/CD
- Nginx for production serving
- Health checks & monitoring

## 📁 Project Structure

```
tutor/
├── frontend/                 # React TypeScript app
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/          # Page components
│   │   ├── contexts/       # React contexts (Auth, Theme)
│   │   ├── services/       # API services
│   │   ├── types/          # TypeScript type definitions
│   │   └── utils/          # Utility functions
│   ├── public/             # Static assets
│   └── Dockerfile          # Frontend container
├── backend/                 # Node.js Express API
│   ├── src/
│   │   ├── controllers/    # Route handlers
│   │   ├── models/         # Database models
│   │   ├── routes/         # API routes
│   │   ├── middleware/     # Custom middleware
│   │   ├── services/       # Business logic
│   │   └── utils/          # Database & utility functions
│   ├── database/           # SQL schema & migrations
│   └── Dockerfile          # Backend container
├── ml-service/             # Python FastAPI ML service
│   ├── src/
│   │   ├── models/         # Pydantic models
│   │   ├── services/       # ML logic
│   │   └── utils/          # Configuration & utilities
│   ├── data/               # Training data
│   └── Dockerfile          # ML service container
├── scripts/                # Development scripts
├── .github/workflows/      # CI/CD pipelines
├── docker-compose.yml      # Development environment
├── Makefile               # Development commands
└── README.md              # Project documentation
```

## 🔧 Development Workflow

### Available Commands

```bash
# Development
make install        # Install all dependencies
make dev           # Start development servers
make build         # Build all components
make test          # Run all tests
make lint          # Run linters
make clean         # Clean build artifacts

# Docker
make docker-build  # Build Docker images
make docker-up     # Start all services
make docker-down   # Stop all services
make logs          # View service logs

# Database
make db-setup      # Initialize databases
make db-reset      # Reset databases

# Quick start
make start         # Build and start everything
make setup         # Full development setup
```

### Service URLs (Development)

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000
- **ML Service:** http://localhost:8001
- **PostgreSQL:** localhost:5432
- **MongoDB:** localhost:27017
- **Redis:** localhost:6379

### Default Login Credentials

```
Email: admin@tutor.app
Password: admin123
```

## 🧪 Testing

### Running Tests

```bash
# All tests
make test

# Individual components
cd backend && npm test
cd frontend && npm test
cd ml-service && python -m pytest
```

### Integration Tests

```bash
# Start services and run integration tests
make docker-up
./scripts/wait-for-services.sh
./scripts/integration-tests.sh
make docker-down
```

## 🚀 Deployment

### Local Production Build

```bash
make docker-build
make docker-up
```

### CI/CD Pipeline

The project includes a comprehensive GitHub Actions pipeline:

1. **Code Quality:** Linting, testing, security scanning
2. **Build:** Docker images for all services
3. **Integration Tests:** Full system testing
4. **Deployment:** Automated staging deployment

### Environment Variables

Create `.env` files in each service directory:

**Backend (.env):**
```env
NODE_ENV=development
PORT=5000
DB_HOST=postgres
DB_NAME=tutor_db
DB_USER=tutor_user
DB_PASSWORD=tutor_password
MONGODB_URI=mongodb://admin:admin123@mongodb:27017/tutor_content?authSource=admin
JWT_SECRET=your-secret-key
REDIS_URL=redis://redis:6379
ML_SERVICE_URL=http://ml-service:8001
```

**Frontend (.env):**
```env
VITE_API_URL=http://localhost:5000/api
VITE_ML_SERVICE_URL=http://localhost:8001
```

**ML Service (.env):**
```env
MONGODB_URL=mongodb://admin:admin123@mongodb:27017/tutor_content?authSource=admin
MODEL_CACHE_DIR=./cache
DEBUG=true
```

## 🎯 Core Features Implementation Status

### ✅ Completed
- Project structure and configuration
- Docker containerization
- Database schemas (PostgreSQL + MongoDB)
- JWT authentication system
- React frontend with Material-UI
- ML service foundation with FastAPI
- CI/CD pipeline with GitHub Actions

### 🚧 In Progress / Next Steps
- **Quiz Management System**
  - Dynamic question generation
  - Real-time quiz taking interface
  - Answer submission and validation
  
- **Progress Tracking**
  - Performance analytics dashboard
  - Learning progress visualization
  - Achievement system

### 🔮 Future Enhancements
- Advanced AI model fine-tuning
- Real-time collaboration features
- Mobile app development
- Advanced analytics and reporting
- Integration with external educational resources

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Code Style

- **Frontend:** ESLint + Prettier
- **Backend:** ESLint + Prettier
- **ML Service:** Black + Flake8
- **Commits:** Conventional Commits format

### Pull Request Process

1. Ensure all tests pass (`make test`)
2. Update documentation as needed
3. Add tests for new features
4. Follow the existing code style
5. Update the CHANGELOG.md

## 🐛 Troubleshooting

### Common Issues

**Port Conflicts:**
```bash
# Check what's using the ports
lsof -i :3000 -i :5000 -i :8001

# Kill processes if needed
make docker-down
```

**Database Connection Issues:**
```bash
# Reset databases
make db-reset

# Check database logs
docker-compose logs postgres
docker-compose logs mongodb
```

**ML Service Issues:**
```bash
# Check ML service logs
docker-compose logs ml-service

# Rebuild ML service
docker-compose build ml-service
```

### Performance Tips

- Use `make dev` for development (hot reload)
- Use `make docker-up` for production-like testing
- Monitor resource usage with `docker stats`
- Use Redis for caching in production

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [Material-UI Documentation](https://mui.com/)
- [Node.js Best Practices](https://github.com/goldbergyoni/nodebestpractices)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

## 📞 Support

For questions or issues:
1. Check this documentation
2. Search existing GitHub issues
3. Create a new issue with detailed information
4. Contact the development team

---

**Happy coding! 🎉**