const express = require('express');
const router = express.Router();
const auth = require('../middleware/auth');
const idempotency = require('../middleware/idempotency');
const authController = require('../controllers/authController');
const userController = require('../controllers/userController');
const notificationController = require('../controllers/notificationController');
const versionController = require('../controllers/versionController');

// Public routes
router.post('/login', authController.login);
router.post('/send-verification-code', authController.sendVerificationCode);
router.get('/version', versionController.checkUpdate);

// Protected routes
router.use(auth);

// User Profile
router.get('/user/profile', userController.getProfile);
router.put('/user/theme', userController.updateTheme);
router.put('/user/language', userController.updateLanguage);

// Account & Security
router.post('/user/change-password', idempotency, authController.changePassword);
router.post('/user/bind', idempotency, authController.bindPhoneEmail);
router.get('/user/devices', authController.getLoginDevices);
router.post('/user/logout-device', authController.logout);

// Notifications
router.get('/notification/preference', notificationController.getPreferences);
router.put('/notification/preference', notificationController.updatePreferences);

module.exports = router;
