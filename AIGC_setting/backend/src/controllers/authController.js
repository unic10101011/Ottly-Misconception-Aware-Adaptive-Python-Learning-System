const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const { User, LoginDevice, VerificationCode } = require('../models');
const { Op } = require('sequelize');

exports.login = async (req, res) => {
  const { username, password, device_id, device_name, system_version, ip_address } = req.body;

  try {
    const user = await User.findOne({ where: { username } });
    if (!user || !(await user.comparePassword(password))) {
      return res.status(401).json({ message: 'Invalid username or password' });
    }

    const accessToken = jwt.sign({ id: user.id }, process.env.JWT_SECRET, { expiresIn: process.env.JWT_EXPIRES_IN });
    const refreshToken = jwt.sign({ id: user.id }, process.env.REFRESH_TOKEN_SECRET, { expiresIn: process.env.REFRESH_TOKEN_EXPIRES_IN });

    const salt = await bcrypt.genSalt(12);
    const refreshTokenHash = await bcrypt.hash(refreshToken, salt);

    await LoginDevice.upsert({
      user_id: user.id,
      device_id,
      device_name,
      system_version,
      ip_address,
      refresh_token_hash: refreshTokenHash,
      status: 'active',
      last_active_at: new Date()
    });

    res.json({ accessToken, refreshToken, user: { id: user.id, username: user.username } });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ message: 'Internal server error' });
  }
};

exports.logout = async (req, res) => {
  const { device_id } = req.body;
  const user_id = req.user.id;

  try {
    const device = await LoginDevice.findOne({ where: { user_id, device_id } });
    if (device) {
      await device.update({ status: 'logged_out', refresh_token_hash: null });
    }

    // Push logout notification (simulated)
    console.log(`Sending logout notification for device ${device_id} of user ${user_id}`);

    res.json({ message: 'Logged out successfully' });
  } catch (error) {
    console.error('Logout error:', error);
    res.status(500).json({ message: 'Internal server error' });
  }
};

exports.getLoginDevices = async (req, res) => {
  const devices = await LoginDevice.findAll({
    where: { user_id: req.user.id, status: 'active' },
    attributes: ['device_id', 'device_name', 'system_version', 'ip_address', 'last_active_at']
  });
  res.json(devices);
};

exports.changePassword = async (req, res) => {
  const { old_password, new_password } = req.body;

  if (!old_password || !new_password) {
    return res.status(400).json({ message: 'Missing passwords' });
  }

  // Password validation: 8-32 characters, uppercase, lowercase, digit, special character
  const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,32}$/;
  if (!passwordRegex.test(new_password)) {
    return res.status(400).json({ message: 'Password does not meet complexity requirements' });
  }

  const isOldPasswordCorrect = await req.user.comparePassword(old_password);
  if (!isOldPasswordCorrect) {
    return res.status(401).json({ message: 'Incorrect current password' });
  }

  // Update password hash
  await req.user.update({ password_hash: new_password });

  // Invalidate all tokens by marking all devices as logged out
  await LoginDevice.update(
    { status: 'logged_out', refresh_token_hash: null },
    { where: { user_id: req.user.id } }
  );

  res.json({ message: 'Password changed successfully, all devices logged out' });
};

exports.bindPhoneEmail = async (req, res) => {
  const { target, code, password, type } = req.body;

  try {
    const isPasswordCorrect = await req.user.comparePassword(password);
    if (!isPasswordCorrect) {
      return res.status(401).json({ message: 'Incorrect current password' });
    }

    const verification = await VerificationCode.findOne({
      where: { target, code, type, expires_at: { [Op.gt]: new Date() } }
    });

    if (!verification) {
      return res.status(400).json({ message: 'Invalid or expired verification code' });
    }

    if (verification.cooldown_until && verification.cooldown_until > new Date()) {
      return res.status(429).json({ message: 'Cooling down, please try again later' });
    }

    if (verification.failed_attempts >= 3) {
      await verification.update({ cooldown_until: new Date(Date.now() + 60000) });
      return res.status(429).json({ message: 'Too many attempts, cooling down for 60 seconds' });
    }

    if (verification.code !== code) {
      await verification.increment('failed_attempts');
      return res.status(400).json({ message: 'Invalid verification code' });
    }

    // Success, update user
    if (target.includes('@')) {
      await req.user.update({ email: target });
    } else {
      await req.user.update({ phone: target });
    }

    await verification.destroy();
    res.json({ message: 'Binding successful' });
  } catch (error) {
    console.error('Binding error:', error);
    res.status(500).json({ message: 'Internal server error' });
  }
};

exports.sendVerificationCode = async (req, res) => {
  const { target, type } = req.body;
  const code = Math.floor(100000 + Math.random() * 900000).toString(); // 6 digits

  await VerificationCode.upsert({
    target,
    code,
    type,
    expires_at: new Date(Date.now() + 5 * 60 * 1000), // 5 min
    failed_attempts: 0
  });

  // Simulated sending (SMS/Email)
  console.log(`Sending verification code ${code} to ${target}`);
  res.json({ message: 'Verification code sent' });
};
