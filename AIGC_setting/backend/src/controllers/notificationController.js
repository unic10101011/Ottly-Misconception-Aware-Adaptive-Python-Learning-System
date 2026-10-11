const { NotificationPref } = require('../models');

exports.getPreferences = async (req, res) => {
  let prefs = await NotificationPref.findOne({ where: { user_id: req.user.id } });
  if (!prefs) {
    prefs = await NotificationPref.create({ user_id: req.user.id });
  }
  res.json(prefs);
};

exports.updatePreferences = async (req, res) => {
  const { push_enabled, system_msg_enabled, activity_msg_enabled, ai_reply_enabled } = req.body;

  let prefs = await NotificationPref.findOne({ where: { user_id: req.user.id } });
  if (!prefs) {
    prefs = await NotificationPref.create({
      user_id: req.user.id,
      push_enabled,
      system_msg_enabled,
      activity_msg_enabled,
      ai_reply_enabled
    });
  } else {
    await prefs.update({
      push_enabled,
      system_msg_enabled,
      activity_msg_enabled,
      ai_reply_enabled,
      version: prefs.version + 1
    });
  }

  // Simulate sync to push gateway
  console.log(`Syncing notification preferences for user ${req.user.id} to push gateway...`);
  // setTimeout(() => console.log('Sync completed.'), 1000);

  res.status(200).json({ message: 'Preferences updated', prefs });
};
