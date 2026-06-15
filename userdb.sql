-- Cybersickness Database Schema
-- Creates a simple database for users, devices, sessions, symptoms, and reports.

CREATE DATABASE IF NOT EXISTS cybersickness
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cybersickness;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(100),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS devices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  device_type VARCHAR(50),
  operating_system VARCHAR(50),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS symptoms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  device_id INT,
  started_at DATETIME NOT NULL,
  ended_at DATETIME,
  location VARCHAR(100),
  notes TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS session_symptoms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  session_id INT NOT NULL,
  symptom_id INT NOT NULL,
  severity TINYINT UNSIGNED NOT NULL CHECK (severity BETWEEN 1 AND 10),
  reported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (symptom_id) REFERENCES symptoms(id) ON DELETE CASCADE,
  UNIQUE KEY uq_session_symptom (session_id, symptom_id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  notify_on_session_completion BOOLEAN NOT NULL DEFAULT TRUE,
  preferred_device_id INT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (preferred_device_id) REFERENCES devices(id) ON DELETE SET NULL
);

INSERT INTO symptoms (name, description) VALUES
  ('Nausea', 'Feeling of sickness with an inclination to vomit'),
  ('Dizziness', 'A sensation of lightheadedness or unsteadiness'),
  ('Eye Strain', 'Discomfort in the eyes after screen exposure'),
  ('Headache', 'Pain or discomfort in the head region')
ON DUPLICATE KEY UPDATE description = VALUES(description);

