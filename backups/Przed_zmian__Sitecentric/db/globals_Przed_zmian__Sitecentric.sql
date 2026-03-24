--
-- PostgreSQL database cluster dump
--

\restrict Rpj650LjkBuoWXOOLgBNA1H88wKv7vTBnZqIuIQTfSXuladN0DF3WO7aKVXGnHg

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE postgres;
ALTER ROLE postgres WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:rI4IPMu4P0vtLENGHCNb/A==$MIcyUYhXCarUZweRYva1y5JdJVys4W2mUH+x8owftzo=:PnYed06yA4DUYzxrBQFJFrwFZQhgEXXvODXltMZ6nlo=';
CREATE ROLE priv_esc;
ALTER ROLE priv_esc WITH SUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:/AuZ8JalP66ZOb05tRHguw==$Zp5o1xKh+IgO26G1ZDuVCMR9a6lwSGiv1IViJ/9vSm4=:rR6TrAJ52OeAzNP2beg9Koe/tWz1kvYGPqm5irZup9o=';

--
-- User Configurations
--


--
-- Role memberships
--

GRANT priv_esc TO postgres WITH INHERIT TRUE GRANTED BY postgres;






\unrestrict Rpj650LjkBuoWXOOLgBNA1H88wKv7vTBnZqIuIQTfSXuladN0DF3WO7aKVXGnHg

--
-- PostgreSQL database cluster dump complete
--

