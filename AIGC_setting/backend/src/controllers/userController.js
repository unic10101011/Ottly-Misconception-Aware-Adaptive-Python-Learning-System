const { User } = require('../models');

exports.updateTheme = async (req, res) => {
  const { theme } = req.body;
  if (!['system', 'light', 'dark'].includes(theme)) {
    return res.status(400).json({ message: 'Invalid theme' });
  }

  await req.user.update({ theme_preference: theme });
  res.json({ message: 'Theme updated successfully' });
};

exports.updateLanguage = async (req, res) => {
  const { language } = req.body;
  if (!['zh-CN', 'en-US'].includes(language)) {
    return res.status(400).json({ message: 'Invalid language' });
  }

  await req.user.update({ lang_preference: language });
  res.json({ message: 'Language updated successfully' });
};

exports.getProfile = async (req, res) => {
  res.json({
    id: req.user.id,
    username: req.user.username,
    phone: req.user.phone,
    email: req.user.email,
    theme: req.user.theme_preference,
    language: req.user.lang_preference
  });
};
