# Email Service Testing Guide

This guide walks you through testing the automated email service feature.

## 📋 Prerequisites

### Backend Setup (Already Running ✅)
Your backend is already running on `http://localhost:8000`

**Environment variables needed in `.env`:**
```bash
# Email settings (already configured)
EMAIL_ENABLED=true
EMAIL_PROVIDER=stub  # Uses StubEmailProvider (logs to console, doesn't send real emails)
EMAIL_FROM_ADDRESS=noreply@thesubtribe.com
EMAIL_FROM_NAME=Subtribe ATS
EMAIL_SEND_TIME_IST=17:00  # 5 PM IST

# Database (should already be set)
DATABASE_URL=postgresql+asyncpg://...
```

### Frontend Setup
1. **Open a new terminal**
2. **Navigate to dashboard:**
   ```bash
   cd /Users/takshilkunadia/Documents/Development/Subtribe/subtribe-dashboard
   ```

3. **Install dependencies (if not done):**
   ```bash
   npm install
   ```

4. **Start the dev server:**
   ```bash
   npm run dev
   ```

   Frontend will run on `http://localhost:3000`

---

## 🧪 Testing Steps

### Step 1: Login to Dashboard
1. Open browser: `http://localhost:3000`
2. Login with your credentials: `akash@thesubtribe.com`

### Step 2: Navigate to an Application
1. Go to **Applications** page or a specific **Job's Applications**
2. Click on any application to view details
3. You should see the application detail page with:
   - Application info
   - Status History
   - **Email History** (new section at the bottom)

### Step 3: Test Interview Invite Email

#### 3.1 Change Status to "Interviewing"
1. On the right sidebar, find **"Update Status"** section
2. Change status dropdown to **"Interviewing"**
3. Add notes (required): e.g., "Moving to interview round"
4. Click **"Update Status"**

#### 3.2 Verify Email Scheduled
**In the Backend Terminal** (where uvicorn is running), you should see:
```
📅 Scheduled interview_invite email for candidate@email.com at 2025-11-26T11:30:00+00:00
```

**In the Dashboard** (Email History section at bottom):
- You should see a new entry with:
  - **Status badge**: "⏰ Pending" (yellow)
  - **Template**: "Interview Invitation"
  - **Subject**: "Interview Invitation - Job Title at Company Name"
  - **Scheduled for**: Tomorrow at 5:00 PM IST
  - **To**: candidate email address

### Step 4: Test Rejection Email

#### 4.1 Change Status to "Rejected"
1. Change status dropdown to **"Rejected"**
2. Add notes: e.g., "Not a good fit for this role"
3. Click **"Update Status"**

#### 4.2 Verify Email Scheduled
**In the Backend Terminal**:
```
🚫 Cancelled 1 pending interview_invite email(s) for application {id}
📅 Scheduled rejection email for candidate@email.com at 2025-11-26T11:30:00+00:00
```

**In the Dashboard**:
- Previous interview invite should show **"Cancelled"** (grey badge)
- New rejection email should show **"⏰ Pending"** (yellow badge)

### Step 5: Manually Trigger Email Send (Testing)

Since emails are scheduled for 5 PM IST tomorrow, let's manually trigger one to see the full flow:

**In the Backend Terminal:**
```bash
cd /Users/takshilkunadia/Documents/Development/Subtribe/subtribe-backend

# Find the scheduled email ID from database
python -c "
import psycopg2
from app.config import settings

db_url = settings.database_url.replace('+asyncpg', '')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

cur.execute('''
    SELECT id, template_type, recipient_email, status, scheduled_for
    FROM scheduled_emails
    WHERE status = 'pending'
    ORDER BY created_at DESC
    LIMIT 3;
''')

print('📧 Recent Scheduled Emails:')
for row in cur.fetchall():
    print(f'  ID: {row[0]}')
    print(f'  Type: {row[1]}')
    print(f'  To: {row[2]}')
    print(f'  Status: {row[3]}')
    print(f'  Scheduled: {row[4]}')
    print()

cur.close()
conn.close()
"
```

**Manually send the email:**
```bash
# Replace {EMAIL_ID} with the ID from above
curl -X POST http://localhost:8000/internal/emails/send \
  -H "Content-Type: application/json" \
  -d '{"scheduled_email_id": "{EMAIL_ID}"}'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Email sent successfully",
  "message_id": "stub-msg-1732537845-abc123"
}
```

**In the Backend Terminal**, you should see:
```
📧 [STUB EMAIL] Sent at 2025-11-25 16:37:25
  From: Subtribe ATS <noreply@thesubtribe.com>
  To: Candidate Name <candidate@email.com>
  Subject: Interview Invitation - Job Title at Company Name
  Message ID: stub-msg-1732537845-abc123
  Body:
Hey Candidate,

Thank you for applying to the Job Title position at Company Name!

We've reviewed your application and would like to invite you to the next round of our hiring process.

We'll reach out to you shortly to coordinate a convenient time for the interview.

We look forward to speaking with you soon!

Best regards,
Company Name Hiring Team

---
This is an automated message from Subtribe ATS. Please do not reply directly to this email.
```

### Step 6: Verify Email Status Updated

**Refresh the application detail page in the dashboard**

The email entry should now show:
- **Status badge**: "✅ Sent" (green)
- **Sent**: "2 minutes ago"
- **Created**: timestamp

---

## 🎯 What to Test

### Basic Flow ✅
- [x] Change status to "interviewing" → Email scheduled
- [x] Change status to "rejected" → Previous email cancelled, new email scheduled
- [x] View email history in dashboard
- [x] Manually trigger email send
- [x] Verify email sent in logs
- [x] Verify status updated in dashboard

### Edge Cases to Test
1. **Multiple status changes before 5 PM:**
   - Change to "interviewing" → Email scheduled
   - Change to "screening" → Email cancelled
   - Change back to "interviewing" → New email scheduled
   - **Expected**: Only the latest email should be pending

2. **Change to non-email statuses:**
   - Change to "screening", "offer", "hired"
   - **Expected**: No emails scheduled (only "interviewing" and "rejected" trigger emails)

3. **Application with no emails yet:**
   - **Expected**: Email History section shows "No emails scheduled yet"

4. **Failed email (simulate):**
   - You can test this by manually updating an email status to "failed" in the database
   - **Expected**: Red "❌ Failed" badge with error message

---

## 🔍 Debugging

### Check Database Directly
```bash
cd /Users/takshilkunadia/Documents/Development/Subtribe/subtribe-backend

python -c "
import psycopg2
from app.config import settings

db_url = settings.database_url.replace('+asyncpg', '')
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Get all scheduled emails for an application
APPLICATION_ID = 'your-app-id-here'

cur.execute('''
    SELECT
        id,
        template_type,
        recipient_email,
        subject,
        status,
        scheduled_for,
        sent_at,
        created_at
    FROM scheduled_emails
    WHERE application_id = %s
    ORDER BY created_at DESC;
''', (APPLICATION_ID,))

print('📧 Scheduled Emails for Application:')
for row in cur.fetchall():
    print(f'  {row[1]} | {row[4]} | To: {row[2]}')
    print(f'  Scheduled: {row[5]} | Sent: {row[6]}')
    print()

cur.close()
conn.close()
"
```

### Check Backend Logs
Look for these log messages in the backend terminal:
- `📧 Scheduled {type} email for {email}` - Email scheduled successfully
- `🚫 Cancelled {count} pending {type} email(s)` - Previous emails cancelled
- `✅ Email sent successfully to {email}` - Email sent
- `❌ Failed to send email to {email}` - Email failed

### Frontend Console
Open browser DevTools (F12) and check Console for:
- API errors (red)
- Network requests to `/applications/{id}/scheduled-emails`

---

## 📝 Test Checklist

- [ ] Backend running on http://localhost:8000
- [ ] Frontend running on http://localhost:3000
- [ ] Can login to dashboard
- [ ] Can view application detail page
- [ ] Email History section appears at bottom
- [ ] Changing status to "interviewing" schedules email
- [ ] Changing status to "rejected" schedules email and cancels previous
- [ ] Email appears in Email History with "Pending" status
- [ ] Backend logs show email scheduled
- [ ] Can manually trigger email send via curl
- [ ] Backend logs show [STUB EMAIL] with full content
- [ ] Dashboard shows email as "Sent" after manual trigger
- [ ] Timestamp updates to "X minutes ago"

---

## 🚀 Production Setup (Future)

When ready for production:

1. **Update `.env`:**
   ```bash
   EMAIL_PROVIDER=sendgrid
   SENDGRID_API_KEY=your-real-api-key
   SENDGRID_SANDBOX_MODE=true  # First test with sandbox mode
   ```

2. **Test with sandbox mode** (validates API, doesn't deliver):
   - Repeat all tests above
   - Emails won't be delivered but API is validated

3. **Go live:**
   ```bash
   SENDGRID_SANDBOX_MODE=false  # Real emails will be sent!
   ```

4. **Set up Google Cloud Tasks** for scheduled sending:
   - Configure GCP_CLOUD_TASKS_QUEUE
   - Configure GCP_CLOUD_TASKS_LOCATION
   - Deploy to Cloud Run

---

## ❓ FAQ

**Q: Emails aren't showing in dashboard?**
A: Check browser console for API errors. Verify backend is running and `/applications/{id}/scheduled-emails` endpoint works.

**Q: No email scheduled when changing status?**
A: Only "interviewing" and "rejected" statuses trigger emails. Other statuses don't schedule emails.

**Q: Previous email not cancelled?**
A: Check database directly. The `_cancel_previous_emails` function should set previous pending emails to "cancelled".

**Q: Want to test real email sending locally?**
A: Use SendGrid with sandbox mode:
```bash
EMAIL_PROVIDER=sendgrid
SENDGRID_SANDBOX_MODE=true
SENDGRID_API_KEY=your-key
```

---

**Need help?** Check the backend logs for detailed error messages, or inspect the database directly using the scripts above.
