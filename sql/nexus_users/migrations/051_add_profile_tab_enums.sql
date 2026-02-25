-- Add missing values to user_profile_tab enum.
-- 'Orders' and 'Rentals' were added as profile tabs but never added to the DB enum.
-- 'Offers' was renamed to 'Orders' — rename existing value and add 'Rentals'.

ALTER TYPE public.user_profile_tab RENAME VALUE 'Offers' TO 'Orders';
ALTER TYPE public.user_profile_tab ADD VALUE IF NOT EXISTS 'Rentals';
