module.exports = (sequelize, DataTypes) => {
  const NotificationPref = sequelize.define('NotificationPref', {
    id: {
      type: DataTypes.BIGINT,
      primaryKey: true,
      autoIncrement: true
    },
    user_id: {
      type: DataTypes.BIGINT,
      allowNull: false
    },
    push_enabled: {
      type: DataTypes.BOOLEAN,
      defaultValue: true
    },
    system_msg_enabled: {
      type: DataTypes.BOOLEAN,
      defaultValue: true
    },
    activity_msg_enabled: {
      type: DataTypes.BOOLEAN,
      defaultValue: true
    },
    ai_reply_enabled: {
      type: DataTypes.BOOLEAN,
      defaultValue: true
    },
    version: {
      type: DataTypes.INTEGER,
      defaultValue: 1
    }
  }, {
    tableName: 'notification_prefs',
    timestamps: true,
    underscored: true
  });

  return NotificationPref;
};
