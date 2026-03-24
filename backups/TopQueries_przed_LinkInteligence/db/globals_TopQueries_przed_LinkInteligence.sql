--
-- PostgreSQL database cluster dump
--

\restrict G8MiHkT9XIGhV4sh4MkuUr1j2ecrQLjBNCC8pQa9fraGHSSAQ6E9ONUOSO1vPuZ

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE postgres;
ALTER ROLE postgres WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:tnqRxZoYmA4ZBDeWLpgA0A==$M/dXKRSTEFjK2bb92xFcQxbWvC+PKfXm3ShW95oiWM0=:GkqwnihapYWfysTS1CFbwvOediHsLL9xexQgOJZtk0U=';

--
-- User Configurations
--








\unrestrict G8MiHkT9XIGhV4sh4MkuUr1j2ecrQLjBNCC8pQa9fraGHSSAQ6E9ONUOSO1vPuZ

--
-- PostgreSQL database cluster dump complete
--

