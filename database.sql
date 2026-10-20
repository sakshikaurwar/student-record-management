-- Student Record Management System
-- Run with a privileged account (local root, or the RDS master user).

CREATE DATABASE IF NOT EXISTS student_management
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE student_management;

CREATE TABLE IF NOT EXISTS students (
  id            INT          NOT NULL AUTO_INCREMENT,
  roll_number   VARCHAR(30)  NOT NULL,
  full_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(150) NOT NULL,
  department    VARCHAR(100) NOT NULL,
  year_of_study INT          NOT NULL,
  phone         VARCHAR(20)  NOT NULL,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_students_roll_number (roll_number)
) ENGINE=InnoDB;

-- Fictional sample data (INSERT IGNORE skips rows whose roll number already exists)
INSERT IGNORE INTO students
  (roll_number, full_name, email, department, year_of_study, phone)
VALUES
  ('IT3001', 'Aarav Deshmukh', 'aarav.deshmukh@example.com', 'Information Technology', 3, '9876500001'),
  ('IT3002', 'Isha Kulkarni',  'isha.kulkarni@example.com',  'Information Technology', 3, '9876500002'),
  ('CS2010', 'Rohan Patil',    'rohan.patil@example.com',    'Computer Science',       2, '9876500003'),
  ('CE1015', 'Sneha Joshi',    'sneha.joshi@example.com',    'Computer Engineering',   1, '9876500004'),
  ('ME4005', 'Kabir Shah',     'kabir.shah@example.com',     'Mechanical Engineering', 4, '9876500005');
