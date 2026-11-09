-- Ejecutar como superusuario (postgres):
--   psql -U postgres -f scripts/crear_bd.sql
-- Crea el rol de la aplicación y la base de datos, de la cual el rol es dueño
-- (así los triggers/vistas quedan bajo el mismo propietario que las tablas).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'empresa_app') THEN
    CREATE ROLE empresa_app LOGIN PASSWORD 'empresa_pass';
  END IF;
END $$;

SELECT 'CREATE DATABASE sistema_empresarial OWNER empresa_app ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'sistema_empresarial')\gexec
