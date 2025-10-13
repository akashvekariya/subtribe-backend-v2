# API Documentation - Subtribe ATS Backend

**Base URL (Production)**: `https://subtribe-ats-api-dev-189393113297.asia-south1.run.app`  
**Base URL (Local)**: `http://localhost:8000`  
**Interactive Docs**: `/docs` (Swagger UI)

---

## Authentication

### Two Methods Supported

**Method 1: HttpOnly Cookie** (Recommended for web browsers)
- Automatically set on login/register
- Secure, XSS-protected
- Browser sends automatically

**Method 2: Authorization Header** (For API clients, curl, Postman)
```
Authorization: Bearer <jwt_token>
```

### Priority
1. Cookie checked first (if present)
2. Falls back to Authorization header
3. Use either method - both work!

### JWT Response Format
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@company.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "admin",
    "company": {
      "id": "uuid",
      "name": "Acme Corp",
      "slug": "acme"
    }
  }
}
```

---

## Endpoints

### Authentication

#### POST /auth/register
Register new user with company code.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe",
  "company_code": "ACME-x7k9p2"
}
```

**Response** `201`:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { ... }
}
```

**Errors**:
- `400` - Invalid company code
- `409` - Email already exists

**Cookie**: Sets `access_token` httpOnly cookie automatically

---

#### POST /auth/login
Login with credentials.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response** `200`:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { ... }
}
```

**Errors**:
- `401` - Invalid credentials

**Cookie**: Sets `access_token` httpOnly cookie automatically

---

#### POST /auth/logout
Logout and clear authentication cookie.

**Response** `200`:
```json
{
  "message": "Successfully logged out"
}
```

**Note**: For API clients using Authorization header, simply discard the token client-side.

---

#### GET /auth/me
Get current user info. 🔒 Auth required

**Response** `200`:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "role": "admin",
  "company": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme",
    "logo_url": "https://...",
    "website_url": "https://acme.com"
  }
}
```

---

### Company

#### GET /companies/me
Get company profile. 🔒 Auth required

**Response** `200`:
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme",
  "invite_code": "ACME-x7k9p2",
  "logo_url": "https://...",
  "website_url": "https://acme.com",
  "tagline": "We build amazing products",
  "about": "Founded in 2020...",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

#### PATCH /companies/me
Update company profile. 🔒 Auth required

**Request** (all fields optional):
```json
{
  "name": "Acme Corporation",
  "logo_url": "https://...",
  "website_url": "https://acme.com",
  "tagline": "Building the future",
  "about": "We are..."
}
```

**Response** `200`: Updated company object

---

### Jobs

#### POST /jobs
Create job posting. 🔒 Auth required

**Request**:
```json
{
  "title": "Senior Backend Engineer",
  "description": "## About the Role\n\nWe're looking for...",
  "position_type": "full_time",
  "location_type": "remote",
  "city": null,
  "country": "India",
  "min_salary": 2000000,
  "max_salary": 3000000,
  "currency": "INR",
  "skills_required": ["Python", "FastAPI", "PostgreSQL"],
  "skills_nice_to_have": ["Docker", "Kubernetes"],
  "min_experience_years": 3,
  "max_experience_years": 8,
  "screening_questions": [
    {
      "id": "q1",
      "type": "text",
      "question": "Why do you want this role?",
      "required": true
    }
  ]
}
```

**Response** `201`:
```json
{
  "id": "uuid",
  "title": "Senior Backend Engineer",
  "slug": "senior-backend-engineer-abc123",
  "status": "draft",
  "description": "...",
  "position_type": "full_time",
  "location_type": "remote",
  "city": null,
  "country": "India",
  "min_salary": 2000000,
  "max_salary": 3000000,
  "currency": "INR",
  "skills_required": ["Python", "FastAPI", "PostgreSQL"],
  "skills_nice_to_have": ["Docker", "Kubernetes"],
  "min_experience_years": 3,
  "max_experience_years": 8,
  "screening_questions": [...],
  "views_count": 0,
  "applications_count": 0,
  "published_at": null,
  "created_at": "2025-01-10T...",
  "updated_at": "2025-01-10T..."
}
```

**Field Types**:
- `position_type`: `full_time` | `part_time` | `contract` | `internship`
- `location_type`: `remote` | `hybrid` | `onsite`
- `status`: `draft` | `active` | `closed`

---

#### GET /jobs
List company jobs. 🔒 Auth required

**Query Params**:
- `status` (optional): `draft` | `active` | `closed`
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page (default: 20, max: 100)

**Response** `200`:
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Senior Backend Engineer",
      "slug": "senior-backend-engineer-abc123",
      "status": "active",
      "position_type": "full_time",
      "location_type": "remote",
      "applications_count": 45,
      "views_count": 1250,
      "published_at": "2025-01-10T...",
      "created_at": "2025-01-09T...",
      "updated_at": "2025-01-10T..."
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 5,
    "pages": 1
  }
}
```

---

#### GET /jobs/{id}
Get job details. 🔒 Auth required

**Response** `200`: Full job object (same as POST response)

**Errors**:
- `404` - Job not found

---

#### PATCH /jobs/{id}
Update job. 🔒 Auth required

**Request** (all fields optional):
```json
{
  "title": "Updated Title",
  "status": "active",
  "description": "..."
}
```

**Response** `200`: Updated job object

**Note**: Changing status to `active` sets `published_at`.

---

#### PATCH /jobs/{id}/close
Close job. 🔒 Auth required

**Response** `200`:
```json
{
  "id": "uuid",
  "status": "closed",
  "closed_at": "2025-01-15T..."
}
```

---

#### GET /public/jobs/{slug}
Public job page. 🌐 No auth required

**Response** `200`:
```json
{
  "id": "uuid",
  "title": "Senior Backend Engineer",
  "slug": "senior-backend-engineer-abc123",
  "description": "...",
  "position_type": "full_time",
  "location_type": "remote",
  "city": null,
  "country": "India",
  "min_salary": 2000000,
  "max_salary": 3000000,
  "currency": "INR",
  "skills_required": ["Python", "FastAPI"],
  "skills_nice_to_have": ["Docker"],
  "min_experience_years": 3,
  "max_experience_years": 8,
  "screening_questions": [...],
  "company": {
    "name": "Acme Corp",
    "slug": "acme",
    "logo_url": "https://...",
    "website_url": "https://acme.com",
    "tagline": "We build amazing products",
    "about": "Founded in 2020..."
  },
  "published_at": "2025-01-10T...",
  "created_at": "2025-01-09T..."
}
```

**Errors**:
- `404` - Job not found or not active

---

### Applications

#### POST /public/jobs/{slug}/apply
Submit application. 🌐 No auth required

**Content-Type**: `multipart/form-data`

**Form Fields**:
- `first_name` (required): string
- `last_name` (required): string
- `email` (required): string
- `phone` (optional): string
- `linkedin_url` (optional): string (URL format)
- `github_url` (optional): string (URL format)
- `portfolio_url` (optional): string (URL format)
- `current_ctc` (optional): integer
- `expected_ctc` (optional): integer
- `notice_period_days` (optional): integer
- `screening_answers` (optional): JSON string `{"q1": "answer", "q2": "answer"}`
- `resume` (required): file (PDF only, max 5MB)

**Example using FormData (JavaScript)**:
```javascript
const formData = new FormData();
formData.append('first_name', 'John');
formData.append('last_name', 'Doe');
formData.append('email', 'john@example.com');
formData.append('phone', '+919876543210');
formData.append('linkedin_url', 'https://linkedin.com/in/johndoe');
formData.append('current_ctc', '1500000');
formData.append('expected_ctc', '2000000');
formData.append('notice_period_days', '30');
formData.append('screening_answers', JSON.stringify({q1: "I love coding"}));
formData.append('resume', fileInput.files[0]);

fetch('/public/jobs/senior-backend-engineer-abc123/apply', {
  method: 'POST',
  body: formData
});
```

**Response** `201`:
```json
{
  "id": "uuid",
  "message": "Application submitted successfully"
}
```

**Errors**:
- `400` - Invalid file type (must be PDF)
- `400` - File too large (max 5MB)
- `404` - Job not found or closed
- `409` - Already applied to this job

---

#### GET /jobs/{job_id}/applications
List applications for job. 🔒 Auth required

**Query Params**:
- `status` (optional): Filter by status
- `page`, `limit`: Pagination

**Response** `200`:
```json
{
  "data": [
    {
      "id": "uuid",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "phone": "+919876543210",
      "status": "applied",
      "current_ctc": 1500000,
      "expected_ctc": 2000000,
      "notice_period_days": 30,
      "applied_at": "2025-01-10T...",
      "created_at": "2025-01-10T...",
      "updated_at": "2025-01-10T..."
    }
  ],
  "pagination": { ... }
}
```

**Application Status Values**:
- `applied` - Initial submission
- `screening` - Under review
- `interviewing` - In interview process
- `offer` - Offer extended
- `hired` - Candidate hired
- `rejected` - Application rejected

---

#### GET /applications/{id}
Get application details. 🔒 Auth required

**Response** `200`:
```json
{
  "id": "uuid",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "+919876543210",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "github_url": "https://github.com/johndoe",
  "portfolio_url": "https://johndoe.com",
  "current_ctc": 1500000,
  "expected_ctc": 2000000,
  "notice_period_days": 30,
  "screening_answers": {
    "q1": "I love coding..."
  },
  "status": "applied",
  "resume_filename": "john_doe_resume.pdf",
  "job": {
    "id": "uuid",
    "title": "Senior Backend Engineer",
    "slug": "senior-backend-engineer-abc123"
  },
  "applied_at": "2025-01-10T...",
  "created_at": "2025-01-10T...",
  "updated_at": "2025-01-10T..."
}
```

**Errors**:
- `404` - Application not found

---

#### PATCH /applications/{id}
Update application status. 🔒 Auth required

**Request**:
```json
{
  "status": "screening",
  "notes": "Moved to screening after resume review"
}
```

**Response** `200`: Updated application object

**Note**: Creates entry in status history.

---

#### GET /applications/{id}/resume/view
Get signed URL to view resume (opens in browser). 🔒 Auth required

**Response** `200`:
```json
{
  "url": "https://storage.googleapis.com/...",
  "filename": "john_doe_resume.pdf",
  "expires_at": "2025-01-10T13:00:00Z"
}
```

**URL Expiry**: 1 hour

---

#### GET /applications/{id}/resume/download
Get signed URL to download resume (forces download). 🔒 Auth required

**Response** `200`: Same format as view endpoint

---

#### GET /applications/{id}/history
Get status change history. 🔒 Auth required

**Response** `200`:
```json
{
  "data": [
    {
      "id": "uuid",
      "from_status": "applied",
      "to_status": "screening",
      "changed_by": {
        "id": "uuid",
        "full_name": "Jane Smith"
      },
      "notes": "Resume looks strong",
      "created_at": "2025-01-11T..."
    },
    {
      "id": "uuid",
      "from_status": null,
      "to_status": "applied",
      "changed_by": null,
      "notes": "Application submitted",
      "created_at": "2025-01-10T..."
    }
  ]
}
```

**Note**: Ordered newest first.

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "type": "validation_error",
    "code": "invalid_email",
    "message": "Invalid email format",
    "details": { ... }
  }
}
```

### Error Types & Status Codes

| HTTP Status | Type | Common Codes |
|-------------|------|--------------|
| 400 | `validation_error` | `invalid_file_type`, `file_too_large`, `invalid_email` |
| 401 | `authentication_error` | `invalid_credentials`, `token_expired`, `invalid_token` |
| 403 | `authorization_error` | `insufficient_permissions` |
| 404 | `not_found_error` | `resource_not_found`, `job_not_found`, `application_not_found` |
| 409 | `conflict_error` | `duplicate_application`, `email_already_exists` |
| 422 | `validation_error` | `invalid_input` |
| 500 | `internal_error` | `server_error` |

---

## Common Patterns

### Pagination
All list endpoints support:
```
?page=1&limit=20
```

Response includes:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 125,
    "pages": 7
  }
}
```

### Date Format
All timestamps are ISO 8601 with timezone:
```
2025-01-10T12:30:45.123Z
```

### File Upload (multipart/form-data)
```javascript
const formData = new FormData();
formData.append('field_name', value);
formData.append('file', fileObject);

fetch(url, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});
```

---

## Quick Integration Checklist

**Authentication Flow**:
1. POST `/auth/login` → Get token
2. Store token in localStorage/sessionStorage
3. Add `Authorization: Bearer ${token}` to all requests
4. On 401 error → Redirect to login

**Job Listing Page**:
1. GET `/jobs?status=active` → Display jobs
2. Click job → Navigate to `/jobs/{id}`
3. GET `/jobs/{id}` → Show details

**Public Job Page**:
1. GET `/public/jobs/{slug}` → Display job + company info
2. Show application form
3. POST `/public/jobs/{slug}/apply` with FormData

**Application Management**:
1. GET `/jobs/{job_id}/applications` → List candidates
2. Click candidate → GET `/applications/{id}`
3. View resume → GET `/applications/{id}/resume/view`
4. Update status → PATCH `/applications/{id}`
5. View history → GET `/applications/{id}/history`

---

**Production URL**: https://subtribe-ats-api-dev-189393113297.asia-south1.run.app  
**Swagger Docs**: Only available in development (http://localhost:8000/docs)  
**Version**: v1.0.1

---

## Security Note

**Production**: `/docs`, `/redoc`, and `/openapi.json` are disabled for security.  
**Development**: Full Swagger UI available at http://localhost:8000/docs

