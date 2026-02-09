-- Migration: Add grants for trade request and bulk trade features

INSERT INTO grants (key, description) VALUES
  ('market.trade', 'Create trade requests to buy/sell items'),
  ('market.bulk', 'Use bulk buy/sell feature to create multiple trade requests at once');
