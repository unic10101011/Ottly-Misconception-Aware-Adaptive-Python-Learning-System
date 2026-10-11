const { AppVersion } = require('../models');

exports.checkUpdate = async (req, res) => {
  const { current_version, platform } = req.query;

  if (!current_version || !platform) {
    return res.status(400).json({ message: 'Missing current_version or platform' });
  }

  try {
    const latestVersion = await AppVersion.findOne({
      where: { platform },
      order: [['version_code', 'DESC']]
    });

    if (!latestVersion) {
      return res.status(404).json({ message: 'No version information found' });
    }

    const isUpdateAvailable = parseInt(latestVersion.version_code) > parseInt(current_version);

    // Simulate grayscale ratio logic
    const userId = req.user ? req.user.id : Math.floor(Math.random() * 1000);
    const inGrayscale = (userId % 100) < parseFloat(latestVersion.grayscale_ratio);

    if (isUpdateAvailable && inGrayscale) {
      return res.json({
        latest_version: latestVersion.version_name,
        latest_version_code: latestVersion.version_code,
        update_log: latestVersion.update_log,
        is_force_update: latestVersion.is_force_update,
        download_url: latestVersion.download_url
      });
    }

    res.json({ message: 'App is up to date' });
  } catch (error) {
    console.error('Check update error:', error);
    res.status(500).json({ message: 'Internal server error' });
  }
};
