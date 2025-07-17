# OptiFuse Server
This repository manages the server-side operations for the OptiFuse platform. OptiFuse is designed to revolutionize the way fusion functions are executed by adapting and optimizing them to deliver significantly faster performance compared to traditional AWS Lambda serverless functions.


## Features

-   GitHub OAuth2 Authentication
-   Securely stores user access tokens
-   API endpoint to fetch a user's repositories

---

## Prerequisites

Before you begin, ensure you have the following installed on your system:

-   [Python](https://www.python.org/downloads/) (3.10 or newer)
-   [PostgreSQL](https://www.postgresql.org/download/) (or access to a PostgreSQL database, e.g., via Supabase)
-   `pip` and `venv` (usually included with Python)

---

## Local Setup Instructions

Follow these steps to get the server running on your local machine.

### 1. Clone the Repository

```bash
git clone <your-server-repo-url>
cd <repository-folder-name>
```

### 2. Set Up the Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

Install all the required Python packages from the `requirements.txt` file.
*(Note: If you don't have a requirements.txt, create one first with `pip freeze > requirements.txt`)*

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

This project uses a `.env` file to manage secret keys and configuration.
Good luck finding this ... hahahaha


### 5. Set Up the Database

Run the Django migrations to create the necessary database tables.

```bash
python manage.py migrate
```

### 6. Run the Server

You're all set! Start the Django development server.

```bash
python manage.py runserver
```

The API will now be running at `http://localhost:8000`.

---

## API Endpoints

-   `POST /api/auth/github/`: Handles the GitHub OAuth callback.
-   `GET /api/repositories/`: Fetches the authenticated user's repositories.