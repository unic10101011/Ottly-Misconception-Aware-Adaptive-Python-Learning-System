-- Database Schema for Mobile App Settings System
CREATE DATABASE IF NOT EXISTS app_settings CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE app_settings;

-- Users Table
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(100) UNIQUE,
    avatar_url VARCHAR(255),
    theme_preference VARCHAR(20) DEFAULT 'system', -- system, light, dark
    lang_preference VARCHAR(10) DEFAULT 'zh-CN', -- zh-CN, en-US
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL -- Soft delete support
) ENGINE=InnoDB;

-- Notification Preferences Table
CREATE TABLE notification_prefs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    push_enabled BOOLEAN DEFAULT TRUE,
    system_msg_enabled BOOLEAN DEFAULT TRUE,
    activity_msg_enabled BOOLEAN DEFAULT TRUE,
    ai_reply_enabled BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1, -- For grayscale and rollback
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB;

-- Login Devices Table
CREATE TABLE login_devices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    device_id VARCHAR(100) NOT NULL, -- Unique device identifier
    device_name VARCHAR(100),
    system_version VARCHAR(50),
    ip_address VARCHAR(45),
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    refresh_token_hash VARCHAR(255),
    status ENUM('active', 'logged_out') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_device (user_id, device_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB;

-- App Versions Table
CREATE TABLE app_versions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    version_code INT NOT NULL,
    version_name VARCHAR(20) NOT NULL,
    update_log TEXT,
    is_force_update BOOLEAN DEFAULT FALSE,
    grayscale_ratio DECIMAL(5,2) DEFAULT 100.00, -- 0.00 to 100.00
    download_url VARCHAR(255),
    platform ENUM('android', 'ios') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_platform_version (platform, version_code)
) ENGINE=InnoDB;

-- Verification Codes Table (for Phone/Email binding)
CREATE TABLE verification_codes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    target VARCHAR(100) NOT NULL, -- phone or email
    code VARCHAR(10) NOT NULL,
    type ENUM('bind', 'unbind', 'reset_password') NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    failed_attempts INT DEFAULT 0,
    cooldown_until TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_target_code (target, code)
) ENGINE=InnoDB;

-- Idempotency Keys Table (for anti-replay and idempotency)
CREATE TABLE idempotency_keys (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    idempotency_key VARCHAR(100) UNIQUE NOT NULL,
    response_body JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
) ENGINE=InnoDB;
