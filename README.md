# Field Updates Hub

Django + Tailwind community platform for agricultural field updates (SmartKing Agri coding challenge).

## Features

- User authentication: register, login, logout
- Field update feed with category filter
- Feed search (title/content/author) and pagination
- Create, edit, and delete updates
- Ownership protections for edit/delete actions
- User profile page with post history and post count
- Responsive UI across auth, feed, profile, edit, and delete pages

## Tech Stack

- Python 3.x
- Django 5.2.11
- TailwindCSS via CDN
- SQLite (default Django database)

## Quick Start

1. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
3. Run migrations:
   ```powershell
   python manage.py migrate
   ```
4. Start the app:
   ```powershell
   $env:DEBUG='True'
   python manage.py runserver
   ```
5. Open:
   - `http://127.0.0.1:8000/`

## Useful Commands

- Django checks:
  ```powershell
  python manage.py check
  ```
- Deploy-oriented security check:
  ```powershell
  $env:DEBUG='False'
  $env:DJANGO_SECRET_KEY='your-long-random-secret-key'
  python manage.py check --deploy
  ```
- Run tests:
  ```powershell
  python manage.py test
  ```

## Project Structure

- `config/` Django project settings and root URL config
- `updates/` app containing models, views, forms, urls, and tests
- `templates/` shared and app templates

## Notes

- For local development, keep `DEBUG=True`.
- Logout uses POST (Django 5+ behavior).
- Category badges use intentional per-category colors for clarity.

## Submission Checklist

- [x] Project runs locally (`python manage.py runserver`)
- [x] Database migrations apply cleanly (`python manage.py migrate`)
- [x] Core functionality implemented:
  - [x] Register/Login/Logout
  - [x] Create/Edit/Delete updates
  - [x] Feed filtering by category
  - [x] Profile page with user post history
- [x] Permission checks enforced for edit/delete ownership
- [x] UI is consistent across major pages
- [x] Tests added and passing (`python manage.py test`)
- [x] Django system checks passing (`python manage.py check`)
- [x] Dependencies pinned in `requirements.txt`
- [x] README includes setup, run, and verification instructions
