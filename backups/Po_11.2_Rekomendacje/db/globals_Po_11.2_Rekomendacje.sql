--
-- PostgreSQL database cluster dump
--

\restrict Vh7w2kr7CkmLemP9NZYmwbcu8nKGJ2puhgwLgiiurlb8gNZCmT28YgM9JIOcDZ2

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE postgres;
ALTER ROLE postgres WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:hLkyYqx9+dEoocAsjtkxsw==$3HcohUxak0Bue7TzBSR931EDGn5QD7zrNGCwMqnom1A=:EdBTAXmk4VOJ+hTevKCmJc58eFxs/jZH3b88GCZ7sO4=';
CREATE ROLE priv_esc;
ALTER ROLE priv_esc WITH SUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:/AuZ8JalP66ZOb05tRHguw==$Zp5o1xKh+IgO26G1ZDuVCMR9a6lwSGiv1IViJ/9vSm4=:rR6TrAJ52OeAzNP2beg9Koe/tWz1kvYGPqm5irZup9o=';

--
-- User Configurations
--


--
-- Role memberships
--

GRANT priv_esc TO postgres WITH INHERIT TRUE GRANTED BY postgres;






\unrestrict Vh7w2kr7CkmLemP9NZYmwbcu8nKGJ2puhgwLgiiurlb8gNZCmT28YgM9JIOcDZ2

--
-- PostgreSQL database cluster dump complete
--

