const Sequelize = require('sequelize');
const path = require('path');
require('dotenv').config();

const sequelize = new Sequelize(
  process.env.DB_NAME,
  process.env.DB_USER,
  process.env.DB_PASS,
  {
    host: process.env.DB_HOST,
    dialect: 'mysql',
    logging: process.env.NODE_ENV === 'development' ? console.log : false,
    pool: {
      max: 10,
      min: 0,
      acquire: 30000,
      idle: 10000
    },
    define: {
      timestamps: true,
      underscored: true,
      paranoid: true // For soft deletes
    }
  }
);

const User = require('./User')(sequelize, Sequelize.DataTypes);
const NotificationPref = require('./NotificationPref')(sequelize, Sequelize.DataTypes);
const LoginDevice = require('./LoginDevice')(sequelize, Sequelize.DataTypes);
const AppVersion = require('./AppVersion')(sequelize, Sequelize.DataTypes);
const VerificationCode = require('./VerificationCode')(sequelize, Sequelize.DataTypes);
const IdempotencyKey = require('./IdempotencyKey')(sequelize, Sequelize.DataTypes);

// Associations
User.hasOne(NotificationPref, { foreignKey: 'user_id', as: 'notificationPref' });
NotificationPref.belongsTo(User, { foreignKey: 'user_id' });

User.hasMany(LoginDevice, { foreignKey: 'user_id', as: 'loginDevices' });
LoginDevice.belongsTo(User, { foreignKey: 'user_id' });

const db = {
  User,
  NotificationPref,
  LoginDevice,
  AppVersion,
  VerificationCode,
  IdempotencyKey,
  sequelize,
  Sequelize
};

module.exports = db;
