# Email Service Implementation Summary

## ✅ Implementation Complete

All phases of the email service have been successfully implemented with zero-tolerance safety features.

---

## 🏗️ Architecture Overview

### Decoupled Design
- Email service is completely isolated in `app/email/` module
- No vendor lock-in: Abstract provider pattern allows easy switching between email services
- Current providers: `StubEmailProvider` (dev/test) and `SendGridEmailProvider` (production)
- Easy to add new providers (AWS SES, Resend, etc.) by extending `EmailProvider` base class

### Multi-Layer Safety Features

#### 1. Feature Flags (app/config.py)
```python
email_enabled: bool = True           # Master switch
email_provider: str = "stub"         # "stub" or "sendgrid"
sendgrid_sandbox_mode: bool = True   # SendGrid sandbox mode
```

#### 2. Staged Rollout Path
1. **Stub Provider**: Logs emails, no actual sending
2. **SendGrid Sandbox**: API validation without delivery
3. **Test Emails**: Send to internal team emails only
4. **Production**: Full rollout

#### 3. Database Audit Trail
Every email operation is tracked in `scheduled_emails` table:
- **Status**: pending → sent/failed/cancelled
- **Timestamps**: scheduled_for, sent_at, created_at
- **Provider Response**: message_id, error_message
- **Metadata**: calendly_link, job_title, etc.

#### 4. Automatic Cancellation
When application status changes multiple times before send time:
- Previous pending emails are automatically cancelled
- Only the latest scheduled email will be sent
- Prevents duplicate/conflicting emails

---

## 📁 File Structure

```
app/
├── email/
│   ├── __init__.py
│   ├── email_service.py          # Core scheduling & sending logic
│   ├── template_renderer.py      # Variable substitution with fallbacks
│   ├── default_templates.py      # Default interview_invite & rejection templates
│   ├── cloud_tasks.py            # Cloud Tasks integration
│   └── providers/
│       ├── __init__.py
│       ├── base.py               # Abstract EmailProvider class
│       ├── stub.py               # StubEmailProvider (dev/test)
│       └── sendgrid_provider.py  # SendGridEmailProvider (production)
│
├── models/
│   ├── email_template.py         # Company-specific custom templates
│   └── scheduled_email.py        # Email audit trail
│
├── routers/
│   └── emails.py                 # Email endpoints (internal + admin)
│
└── config.py                     # Email feature flags

database/migrations/versions/
└── 6698861bf4ae_add_email_templates_and_scheduled_emails.py
```

---

## 🗄️ Database Schema

### `email_templates` Table
Stores company-specific custom email templates (optional).

**Columns:**
- `id`: UUID primary key
- `company_id`: Foreign key to companies
- `template_type`: 'interview_invite' or 'rejection'
- `subject`: Template subject with {variable} placeholders
- `body`: Template body (plain text only)
- `created_at`, `updated_at`: Timestamps

**Constraints:**
- Unique constraint on (company_id, template_type)
- Check constraint on template_type values

### `scheduled_emails` Table
Tracks all scheduled and sent emails with full audit trail.

**Columns:**
- `id`: UUID primary key
- `application_id`: Foreign key to applications
- `company_id`: Foreign key to companies
- `template_type`: 'interview_invite' or 'rejection'
- `recipient_email`, `recipient_name`: Recipient info
- `subject`, `body`: Rendered email content (after variable substitution)
- `scheduled_for`: When to send (5 PM IST next day)
- `status`: 'pending', 'sent', 'failed', or 'cancelled'
- `sent_at`: Actual send timestamp
- `provider_message_id`: SendGrid message ID
- `error_message`: Error details if failed
- `metadata`: JSONB (calendly_link, job_title, etc.)
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `idx_scheduled_emails_status_time`: (status, scheduled_for) for Cloud Tasks queries
- `idx_scheduled_emails_application`: (application_id) for application history

---

## 📧 Email Templates

### Default Templates

#### Interview Invite
```
Subject: Interview Invitation - {job_title} at {company_name}

Body:
Hey {candidate_name},

Thank you for applying to the {job_title} position at {company_name}!

We've reviewed your application and would like to invite you to the next round.

Please use the following link to schedule your interview:
{calendly_link}

We look forward to speaking with you soon!

Best regards,
{company_name} Hiring Team
```

#### Rejection
```
Subject: Update on Your Application - {job_title} at {company_name}

Body:
Hey {candidate_name},

Thank you for taking the time to apply for the {job_title} position at {company_name}.

After careful consideration, we have decided to move forward with other candidates.

We appreciate your interest and encourage you to apply for future opportunities.

Best regards,
{company_name} Hiring Team
```

### Template Variables
- `{candidate_name}`: Falls back to "there" if missing
- `{company_name}`: Falls back to "our team" if missing
- `{job_title}`: Falls back to "the position" if missing
- `{calendly_link}`: Required for interview invites

### Custom Templates
Companies can override defaults via API:
- `PUT /companies/{id}/email-templates`: Create/update custom template
- `DELETE /companies/{id}/email-templates/{type}`: Revert to default

---

## 🔌 API Endpoints

### Internal Endpoint (Cloud Tasks)
**POST /internal/emails/send**
- Called by Cloud Tasks at scheduled time (5 PM IST)
- Sends the email and updates status
- Idempotent: Won't send twice even if task retries

```json
Request:
{
  "scheduled_email_id": "uuid"
}

Response:
{
  "success": true,
  "message": "Email sent successfully",
  "message_id": "sendgrid-message-id"
}
```

### Admin Endpoints (Template Management)

**GET /companies/{company_id}/email-templates**
- List all custom templates for company
- Indicates which templates use defaults

**PUT /companies/{company_id}/email-templates**
- Create or update custom template

```json
Request:
{
  "template_type": "interview_invite",
  "subject": "Custom subject with {variables}",
  "body": "Custom body..."
}
```

**DELETE /companies/{company_id}/email-templates/{template_type}**
- Delete custom template (reverts to default)

### Application Status Update (Enhanced)

**PATCH /applications/{id}**
- Now triggers email scheduling on status change
- Requires `calendly_link` when status = "interviewing"

```json
Request:
{
  "status": "interviewing",
  "notes": "Great candidate, scheduling interview",
  "calendly_link": "https://calendly.com/company/interview"
}
```

**Email Scheduling Logic:**
- Status → "interviewing": Schedules interview_invite email
- Status → "rejected": Schedules rejection email
- Emails scheduled for 5 PM IST next day
- Previous pending emails automatically cancelled

---

## 🚀 Email Flow

### 1. Status Change Triggers Email
```
Recruiter updates application status to "interviewing"
  ↓
Application endpoint validates calendly_link provided
  ↓
EmailService.schedule_email() called
  ↓
- Cancel any previous pending emails for this application
- Get email template (custom or default)
- Render template with variables + fallbacks
- Calculate send time (5 PM IST next day)
- Create ScheduledEmail record (status=pending)
- Create Cloud Task to trigger send
```

### 2. Cloud Tasks Triggers Send
```
5 PM IST arrives
  ↓
Cloud Tasks calls POST /internal/emails/send
  ↓
EmailService.send_scheduled_email() called
  ↓
- Fetch ScheduledEmail record
- Verify status = pending
- Build EmailMessage
- Send via configured provider (stub or sendgrid)
- Update status to "sent" or "failed"
- Store provider_message_id or error_message
```

### 3. Email Providers

**StubEmailProvider:**
- Logs email to console with full details
- Returns mock message_id
- Never actually sends

**SendGridEmailProvider:**
- Sends via SendGrid API
- Supports sandbox mode (validates but doesn't deliver)
- Returns actual SendGrid message_id
- Handles rate limits and retries

---

## 🧪 Testing Guide

### Phase 1: Stub Provider Testing

**Configuration (.env):**
```bash
EMAIL_ENABLED=true
EMAIL_PROVIDER=stub
```

**Test Flow:**
1. Start server: `uvicorn app.main:app --reload`
2. Update application status to "interviewing":
   ```bash
   curl -X PATCH http://localhost:8000/applications/{id} \
     -H "Authorization: Bearer {token}" \
     -H "Content-Type: application/json" \
     -d '{
       "status": "interviewing",
       "notes": "Scheduling interview",
       "calendly_link": "https://calendly.com/test/interview"
     }'
   ```
3. Check logs for email details:
   ```
   📧 [STUB EMAIL] Sent at 2025-11-25T12:00:00
     From: Subtribe ATS <noreply@thesubtribe.com>
     To: John Doe <john@example.com>
     Subject: Interview Invitation - Software Engineer at Acme Inc
     Message ID: stub-abc-123
     Body:
     Hey John,

     Thank you for applying to the Software Engineer position at Acme Inc!
     ...
   ```

4. Check database:
   ```sql
   SELECT * FROM scheduled_emails WHERE application_id = '{id}';
   ```
   - Verify `status = 'pending'`
   - Verify `scheduled_for` is next day 5 PM IST
   - Verify `metadata` contains calendly_link

5. Manually trigger send (simulate Cloud Tasks):
   ```bash
   curl -X POST http://localhost:8000/internal/emails/send \
     -H "Content-Type: application/json" \
     -d '{"scheduled_email_id": "{scheduled_email_id}"}'
   ```

6. Check logs again for send confirmation
7. Check database: `status` should be 'sent'

### Phase 2: SendGrid Sandbox Testing

**Configuration (.env):**
```bash
EMAIL_ENABLED=true
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=your-actual-api-key
SENDGRID_SANDBOX_MODE=true
```

**Test Flow:**
- Same as Phase 1, but emails are validated by SendGrid without delivery
- Check logs for `[SENDGRID SANDBOX]` messages
- Verify SendGrid dashboard shows sandbox requests

### Phase 3: Live Email Testing

**Configuration (.env):**
```bash
EMAIL_ENABLED=true
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=your-actual-api-key
SENDGRID_SANDBOX_MODE=false
```

**⚠️ IMPORTANT:**
- Test with internal team emails ONLY
- Update test application with your email address
- Verify emails actually arrive in inbox

### Phase 4: Cloud Tasks Integration

**Setup Cloud Tasks Queue:**
```bash
gcloud tasks queues create email-queue \
  --location=asia-south1 \
  --max-attempts=3 \
  --min-backoff=30s
```

**Deploy to Cloud Run and test full flow:**
1. Update application status
2. Wait for scheduled time (or adjust config for testing)
3. Cloud Tasks automatically triggers send
4. Verify email received and database updated

---

## ⚙️ Configuration Reference

### Environment Variables

```bash
# Email Service
EMAIL_ENABLED=true                            # Master switch
EMAIL_PROVIDER=stub                           # "stub" or "sendgrid"
EMAIL_FROM_ADDRESS=noreply@thesubtribe.com    # Sender email
EMAIL_FROM_NAME=Subtribe ATS                  # Sender name
SENDGRID_API_KEY=SG.xxx                       # SendGrid API key (required)
SENDGRID_SANDBOX_MODE=true                    # Sandbox mode toggle
GCP_CLOUD_TASKS_QUEUE=email-queue             # Cloud Tasks queue name
GCP_CLOUD_TASKS_LOCATION=asia-south1          # Cloud Tasks location
EMAIL_SEND_TIME_IST=17:00                     # Send time (HH:MM IST)
```

### Feature Flag Combinations

| EMAIL_ENABLED | EMAIL_PROVIDER | SENDGRID_SANDBOX_MODE | Result |
|---------------|----------------|----------------------|--------|
| false | * | * | No emails sent |
| true | stub | * | Emails logged only |
| true | sendgrid | true | SendGrid validates, no delivery |
| true | sendgrid | false | **Live emails sent** |

---

## 🔒 Safety Checklist

- [x] Master email_enabled flag
- [x] Stub provider for dev/test
- [x] SendGrid sandbox mode
- [x] Automatic email cancellation on status re-changes
- [x] Database audit trail (scheduled_emails table)
- [x] Idempotent send endpoint (won't send twice)
- [x] Error logging (doesn't fail status update)
- [x] Template variable fallbacks (graceful degradation)
- [x] Calendly link validation (required for interviews)
- [x] Plain text only (no HTML complexity)

---

## 📊 Monitoring & Debugging

### Check Scheduled Emails
```sql
-- Pending emails
SELECT * FROM scheduled_emails
WHERE status = 'pending'
ORDER BY scheduled_for;

-- Failed emails
SELECT * FROM scheduled_emails
WHERE status = 'failed'
ORDER BY created_at DESC;

-- Email history for application
SELECT * FROM scheduled_emails
WHERE application_id = 'uuid'
ORDER BY created_at DESC;
```

### Check Logs
```bash
# Stub email sends
grep "STUB EMAIL" logs/app.log

# SendGrid sends
grep "SENDGRID" logs/app.log

# Email scheduling
grep "Scheduled.*email" logs/app.log

# Errors
grep "Failed to.*email" logs/app.log
```

---

## 🚦 Rollout Plan

### Day 1-2: Stub Provider Testing
- Deploy with `EMAIL_PROVIDER=stub`
- Test full flow: status change → schedule → send
- Verify logs and database records
- Test cancellation logic (change status multiple times)

### Day 3: SendGrid Sandbox Testing
- Switch to `EMAIL_PROVIDER=sendgrid`, `SENDGRID_SANDBOX_MODE=true`
- Verify API integration works
- Check SendGrid dashboard for validation requests

### Day 4-5: Internal Team Testing
- Switch to `SENDGRID_SANDBOX_MODE=false`
- Test with internal emails only
- Verify actual email delivery
- Test all template variables and fallbacks

### Day 6: Cloud Tasks Integration
- Create Cloud Tasks queue
- Deploy to staging environment
- Test scheduled sends at 5 PM IST

### Day 7+: Production Rollout
- Deploy to production
- Monitor scheduled_emails table
- Check SendGrid delivery stats
- Gather feedback from recruiters

---

## 🛠️ Troubleshooting

### Email not scheduled
- Check `EMAIL_ENABLED` flag
- Verify status changed to "interviewing" or "rejected"
- Check application logs for errors
- Query `scheduled_emails` table

### Email scheduled but not sent
- Check Cloud Tasks queue for errors
- Verify `/internal/emails/send` endpoint accessible
- Check scheduled email status in database
- Review provider logs (SendGrid API errors)

### Wrong template used
- Check if company has custom template
- Verify template_type matches status change
- Review default_templates.py

### Variables not substituted
- Check template contains correct {variable_name} syntax
- Verify variables provided in metadata
- Check fallback values in default_templates.py

---

## 📝 Next Steps / V2 Features

### Potential Enhancements
- [ ] Email preview endpoint for recruiters
- [ ] Bulk email scheduling (multiple candidates)
- [ ] Email analytics (open rates, click tracking)
- [ ] Additional template types (offer letter, follow-up)
- [ ] Rich text/HTML emails (carefully!)
- [ ] Attachment support (offer letters, etc.)
- [ ] Email bounce handling
- [ ] Unsubscribe management
- [ ] A/B testing for templates
- [ ] Scheduled email editing (before send time)

### Additional Providers
- [ ] AWS SES provider
- [ ] Resend provider
- [ ] Postmark provider
- [ ] Mailgun provider

---

## ✅ Implementation Checklist

- [x] Database schema (email_templates, scheduled_emails)
- [x] Alembic migration
- [x] Abstract EmailProvider base class
- [x] StubEmailProvider implementation
- [x] SendGridEmailProvider implementation
- [x] Template renderer with variable substitution
- [x] Default email templates
- [x] EmailService with scheduling logic
- [x] Cloud Tasks scheduler integration
- [x] Application status endpoint integration
- [x] Internal email send endpoint
- [x] Email template management API
- [x] Configuration and feature flags
- [x] Dependencies (sendgrid, google-cloud-tasks, pytz)

**Status: 🎉 IMPLEMENTATION COMPLETE**

All email service features have been implemented with zero-tolerance safety measures. Ready for testing with stub provider.
