# Contributing Guidelines

## Getting Started

- Fork the repository
- Create a feature branch (`git checkout -b feature/AmazingFeature`)
- Commit your changes (`git commit -m 'Add some AmazingFeature'`)
- Push to the branch (`git push origin feature/AmazingFeature`)
- Open a Pull Request

## Development Setup

1. Clone the repo: `git clone https://github.com/yourusername/km003c-protocol-research.git`
2. Install dependencies: `uv sync --dev`
3. Run tests: `just test`
4. Format code: `just format`

## Code Standards

- Follow PEP 8 for Python
- Use `black` and `isort` for formatting
- Write tests for new features
- Update documentation as needed