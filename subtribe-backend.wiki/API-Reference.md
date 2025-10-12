# API Reference

Complete API endpoint reference for Subtribe ATS backend.

---

## Base URL

**Local**: `http://localhost:8000`  
**Production**: `https://your-api.run.app`

**API Docs**: `/docs` (Swagger UI)

---

## Authentication

### Bearer Token
All protected endpoints require JWT in header:
```
Authorization: Bearer <token>
```

### JWT Claims
```json
{
  "user_id": "uuid",
  "company_id": "uuid",
  "role": "admin",
  "email": "user@company.com",
  "exp": 1234567890
}
```

**Token Expiry**: 15 days  
**Refresh**: Not implemented in V1

---

## Endpoints

### Authentication

#### `POST /auth/register`
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

**Response**: `201 Created`
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "uuid", "email": "...", ... }
}
```

**Errors**:
- `400` Invalid company code
- `409` Email already registered

---

#### `POST /auth/login`
Login with email and password.

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response**: `200 OK`
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "uuid", "email": "...", ... }
}
```

**Errors**:
- `401` Invalid credentials

---

#### `GET /auth/me`
Get current authenticated user.

**Auth**: Required

**Response**: `200 OK`
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
    "slug": "acme"
  }
}
```

---

### Companies

#### `GET /companies/me`
Get current company profile.

**Auth**: Required

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme",
  "logo_url": "https://...",
  "website_url": "https://acme.com",
  "tagline": "We build amazing products",
  "about": "Founded in 2020..."
}
```

---

#### `PATCH /companies/me`
Update company profile.

**Auth**: Required (admin only)

**Request**:
```json
{
  "name": "Acme Corporation",
  "logo_url": "https://...",
  "tagline": "Building the future",
  "about": "Updated description",
  "website_url": "https://newdomain.com"
}
```

**Response**: `200 OK` (updated company object)

**Errors**:
- `422` Invalid URL format

---

### Jobs

#### `POST /jobs`
Create new job posting.

**Auth**: Required

**Request**:
```json
{
  "title": "Senior Backend Engineer",
  "description": "We're looking for...",
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
  "screening_questions": [...]
}
```

**Response**: `201 Created`
```json
{
  "id": "uuid",
  "title": "Senior Backend Engineer",
  "slug": "senior-backend-engineer-abc123",
  "status": "draft",
  ...
}
```

---

#### `GET /jobs`
List company's jobs.

**Auth**: Required

**Query Parameters**:
- `status` (optional): `draft`, `active`, `closed`
- `page` (optional): Page number (default: 1)
- `limit` (optional): Items per page (default: 20, max: 100)

**Response**: `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Senior Backend Engineer",
      "slug": "...",
      "status": "active",
      "applications_count": 45,
      "views_count": 1250,
      "published_at": "2025-01-10T...",
      "created_at": "2025-01-09T..."
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

#### `GET /jobs/{id}`
Get job details.

**Auth**: Required

**Response**: `200 OK` (full job object)

**Errors**:
- `404` Job not found
- `403` Job belongs to another company

---

#### `PATCH /jobs/{id}`
Update job.

**Auth**: Required

**Request**: Partial job object (any fields)

**Response**: `200 OK` (updated job)

**Note**: Changing status to `active` sets `published_at`.

---

#### `PATCH /jobs/{id}/close`
Close job (stop accepting applications).

**Auth**: Required

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "status": "closed",
  "closed_at": "2025-01-15T..."
}
```

---

#### `GET /public/jobs/{slug}` 🌐
Public job page (no auth required).

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "title": "Senior Backend Engineer",
  "description": "...",
  "company": {
    "name": "Acme Corp",
    "logo_url": "...",
    "website_url": "...",
    "tagline": "..."
  },
  ...
}
```

**Note**: Increments `views_count` on each request.

**Errors**:
- `404` Job not found or not active

---

### Applications

#### `POST /public/jobs/{slug}/apply` 🌐
Submit job application (no auth required).

**Content-Type**: `multipart/form-data`

**Fields**:
- `first_name` (required)
- `last_name` (required)
- `email` (required)
- `phone` (optional)
- `linkedin_url` (optional)
- `github_url` (optional)
- `portfolio_url` (optional)
- `current_ctc` (optional)
- `expected_ctc` (optional)
- `notice_period_days` (optional)
- `screening_answers` (optional, JSON string)
- `resume` (required, PDF only, max 5MB)

**Response**: `201 Created`
```json
{
  "id": "uuid",
  "message": "Application submitted successfully"
}
```

**Errors**:
- `400` Invalid file type (must be PDF)
- `400` File too large (max 5MB)
- `404` Job not found or closed
- `409` Already applied to this job

---

#### `GET /jobs/{job_id}/applications`
List applications for a job.

**Auth**: Required

**Query Parameters**:
- `status` (optional): Filter by status
- `page`, `limit`: Pagination

**Response**: `200 OK`
```json
{
  "data": [
    {
      "id": "uuid",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "status": "applied",
      "applied_at": "2025-01-10T..."
    }
  ],
  "pagination": { ... }
}
```

---

#### `GET /applications/{id}`
Get application details.

**Auth**: Required

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "phone": "...",
  "linkedin_url": "...",
  "current_ctc": 1500000,
  "expected_ctc": 2000000,
  "notice_period_days": 30,
  "screening_answers": { ... },
  "status": "applied",
  "job": {
    "id": "uuid",
    "title": "...",
    "slug": "..."
  },
  "applied_at": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

---

#### `PATCH /applications/{id}`
Update application status.

**Auth**: Required

**Request**:
```json
{
  "status": "screening",
  "notes": "Moved to screening after resume review"
}
```

**Response**: `200 OK` (updated application)

**Note**: Creates entry in status history.

---

#### `GET /applications/{id}/resume/view`
Get signed URL to view resume (inline).

**Auth**: Required

**Response**: `200 OK`
```json
{
  "url": "https://storage.googleapis.com/...",
  "filename": "john_doe_resume.pdf",
  "expires_at": "2025-01-10T12:00:00Z"
}
```

**Expiry**: 1 hour

---

#### `GET /applications/{id}/resume/download`
Get signed URL to download resume (attachment).

**Auth**: Required

**Response**: `200 OK` (same format as view)

---

#### `GET /applications/{id}/history`
Get status change history.

**Auth**: Required

**Response**: `200 OK`
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

### Error Types

| Type | HTTP Status | Description |
|------|-------------|-------------|
| `validation_error` | 422 | Invalid request data |
| `authentication_error` | 401 | Missing/invalid token |
| `authorization_error` | 403 | Insufficient permissions |
| `not_found_error` | 404 | Resource not found |
| `conflict_error` | 409 | Resource already exists |
| `internal_error` | 500 | Server error |

### Common Error Codes

- `invalid_credentials` - Wrong email/password
- `token_expired` - JWT expired
- `invalid_token` - Malformed JWT
- `insufficient_permissions` - Wrong role for action
- `resource_not_found` - Entity doesn't exist
- `duplicate_entry` - Unique constraint violation
- `invalid_file_type` - Wrong file format
- `file_too_large` - File exceeds size limit

---

## Rate Limiting

**Current**: No rate limiting in V1

**Future**: 100 requests/minute per IP (V1.1)

---

## Pagination

Standard pagination for list endpoints:

**Request**:
```
GET /jobs?page=2&limit=50
```

**Response**:
```json
{
  "data": [ ... ],
  "pagination": {
    "page": 2,
    "limit": 50,
    "total": 125,
    "pages": 3
  }
}
```

**Defaults**: page=1, limit=20  
**Max Limit**: 100

---

## Status Values

### Job Status
- `draft` - Not published
- `active` - Accepting applications
- `closed` - No longer accepting applications

### Application Status
- `applied` - Initial submission
- `screening` - Under review
- `interviewing` - In interview process
- `offer` - Offer extended
- `hired` - Candidate hired
- `rejected` - Application rejected

---

**Related**:
- [Authentication](Authentication)
- [Database Schema](Database-Schema)
- [Architecture](Architecture)

