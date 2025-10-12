-- RLS Policies for Subtribe ATS
-- Run in Supabase SQL Editor after migrations
-- Safe to run multiple times (idempotent using DROP IF EXISTS)

-- Enable RLS on all tables
ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_status_history ENABLE ROW LEVEL SECURITY;

-- Create permissive policies (service role has full access)
-- MVP uses application-level filtering, these just remove "Unrestricted" warnings
-- Using DROP IF EXISTS makes this script idempotent (safe to run multiple times)

DROP POLICY IF EXISTS allow_service_role_all ON alembic_version;
CREATE POLICY allow_service_role_all ON alembic_version
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS allow_service_role_all ON companies;
CREATE POLICY allow_service_role_all ON companies
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS allow_service_role_all ON users;
CREATE POLICY allow_service_role_all ON users
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS allow_service_role_all ON jobs;
CREATE POLICY allow_service_role_all ON jobs
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS allow_service_role_all ON applications;
CREATE POLICY allow_service_role_all ON applications
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS allow_service_role_all ON application_status_history;
CREATE POLICY allow_service_role_all ON application_status_history
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Verify RLS is enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN ('alembic_version', 'companies', 'users', 'jobs', 'applications', 'application_status_history');

-- Verify policies exist
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE tablename IN ('alembic_version', 'companies', 'users', 'jobs', 'applications', 'application_status_history');

