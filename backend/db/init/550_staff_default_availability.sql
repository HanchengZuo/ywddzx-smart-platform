-- Distinguish lazy system defaults from an operator's explicit availability.
ALTER TABLE staff_availability ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE;
