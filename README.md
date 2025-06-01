# SaaS Content Generation Application

This project is a SaaS content generation application built using Python and FastAPI. It leverages the Gemini API for content generation and provides a robust backend for user authentication, content management, and user management.

## Features

- User authentication (login and registration)
- Content generation endpoints
- User profile management
- Secure password handling and token generation

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd saas-content-generator
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables in the `.env` file, including your Gemini API key.

## Running the Application

To run the application, execute the following command:

```bash
uvicorn src.main:app --reload
```

## Testing

To run the tests, use the following command:

```bash
pytest
```

## License

This project is licensed under the MIT License.