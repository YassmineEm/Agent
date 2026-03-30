# Meta-Chatbot Generation System Dashboard

A Django-based dashboard for configuring and deploying specialized AI chatbot agents with modular capabilities (SQL, RAG, Actions).

## Features

- **Identity Configuration**: Define chatbot name, role, and guardrails
- **SQL Agent**: Connect to multiple databases (PostgreSQL, MySQL, SQLite, MSSQL, Oracle)
- **RAG Agent**: Configure document retrieval with reranking and query expansion
- **Action Agent**: Integrate external APIs and tools
- **Dynamic UI**: Alpine.js for state management, HTMX for dynamic row injection
- **LLM Support**: Qwen3:8b, Gemma3, Phi4

## Tech Stack

- **Backend**: Django 5.0.3, Python 3.12+
- **Frontend**: Tailwind CSS, Alpine.js, HTMX
- **Database**: SQLite (default) / PostgreSQL

## Installation

### Prerequisites

- Python 3.12 or higher
- pip
- Virtual environment support

### Windows Setup

```bash
# Run the setup script
setup.bat
```

### Linux/Mac Setup

```bash
# Make the script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

### Manual Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## Project Structure

```
meta-chatbot-dashboard/
├── manage.py
├── requirements.txt
├── README.md
├── setup.sh / setup.bat
├── meta_chatbot/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── dashboard/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── forms.py
    ├── migrations/
    └── templates/
        └── dashboard/
            ├── base.html
            ├── index.html
            ├── chatbot_detail.html
            ├── chatbot_form.html
            ├── chatbot_confirm_delete.html
            └── partials/
                ├── sql_row.html
                └── action_row.html
```

## Usage

### Creating a Chatbot

1. Navigate to the dashboard home page
2. Click "New Chatbot" button
3. Fill in the identity configuration:
   - Name
   - Description
   - Base Model (Qwen3:8b, Gemma3, Phi4)
   - System Role (prompt)
   - Guardrails

4. Enable desired capabilities:
   - **SQL Agent**: Check the box and add database connections
   - **RAG Agent**: Check the box and configure retrieval settings
   - **Action Agent**: Check the box and add API integrations

5. Click "Create Chatbot"

### Managing SQL Connections

- Click "Add Database Connection" to add multiple databases
- Supported types: PostgreSQL, MySQL, SQLite, MSSQL, Oracle
- Enter connection strings in the format: `postgresql://user:pass@host:port/dbname`

### Configuring RAG

- Set Top-K value (number of documents to retrieve)
- Enable Reranker for semantic reranking
- Enable Query Expansion for better retrieval
- Specify embedding model

### Adding Actions

- Click "Add Action" to define API integrations
- Configure HTTP method, endpoint, headers, and payload template
- Actions allow the chatbot to interact with external services

## API Models

### Chatbot
- Identity configuration
- Module activation flags
- Base model selection

### SQLAgent
- Multiple database connections per chatbot
- Support for various database types

### RAGAgent
- Document retrieval configuration
- Reranking and query expansion options

### ActionAgent
- API/Tool integrations
- HTTP method configuration
- Custom headers and payloads

## Development

### Running Tests

```bash
python manage.py test
```

### Creating Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Admin Interface

Access the Django admin at `http://localhost:8000/admin/` with your superuser credentials.

## Configuration

Edit `meta_chatbot/settings.py` to configure:
- Database settings
- Static files
- Allowed hosts
- Debug mode

## Security Notes

- Change `SECRET_KEY` in production
- Set `DEBUG = False` in production
- Configure `ALLOWED_HOSTS`
- Use environment variables for sensitive data
- Encrypt database connection strings

## License

MIT License

## Support

For issues and questions, please open an issue on the repository.