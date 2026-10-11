const jwt = require('jsonwebtoken');
const { User, LoginDevice } = require('../models');

const auth = async (req, res, next) => {
  try {
    const authHeader = req.header('Authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ message: 'Authentication required' });
    }

    const token = authHeader.replace('Bearer ', '');
    const decoded = jwt.verify(token, process.env.JWT_SECRET);

    const user = await User.findByPk(decoded.id);
    if (!user) {
      return res.status(401).json({ message: 'User not found' });
    }

    // Check if the device is still active (for forced logout)
    const deviceId = req.header('X-Device-ID');
    if (deviceId) {
      const device = await LoginDevice.findOne({
        where: { user_id: user.id, device_id: deviceId, status: 'active' }
      });
      if (!device) {
        return res.status(401).json({ message: 'Device logged out' });
      }
      req.device = device;
    }

    req.user = user;
    req.token = token;
    next();
  } catch (error) {
    res.status(401).json({ message: 'Invalid or expired token' });
  }
};

module.exports = auth;
