--
-- PostgreSQL database cluster dump
--

\restrict H7ALKvFfDXSpsaHJS4PDGCnEzgigBPKI1owJYFyGtC4WvbHTO0iRGw095xTOumP

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE postgres;
ALTER ROLE postgres WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:BW2gMufAdW0rZ8j28Xz8PQ==$gnElz/+FBD/4SDBRR1ghmW/wbqZjFZzlCFSJ8fRVvko=:LBsTZSSFQwzn1YpPXWF1eWsGzW+v8p7HZiNqs29pS+8=';
CREATE ROLE priv_esc;
ALTER ROLE priv_esc WITH SUPERUSER INHERIT NOCREATEROLE NOCREATEDB LOGIN NOREPLICATION NOBYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:/AuZ8JalP66ZOb05tRHguw==$Zp5o1xKh+IgO26G1ZDuVCMR9a6lwSGiv1IViJ/9vSm4=:rR6TrAJ52OeAzNP2beg9Koe/tWz1kvYGPqm5irZup9o=';

--
-- User Configurations
--


--
-- Role memberships
--

GRANT priv_esc TO postgres WITH INHERIT TRUE GRANTED BY postgres;






\unrestrict H7ALKvFfDXSpsaHJS4PDGCnEzgigBPKI1owJYFyGtC4WvbHTO0iRGw095xTOumP

--
-- PostgreSQL database cluster dump complete
--

