module.exports = (sequelize, DataTypes) => {
  const LoginDevice = sequelize.define('LoginDevice', {
    id: {
      type: DataTypes.BIGINT,
      primaryKey: true,
      autoIncrement: true
    },
    user_id: {
      type: DataTypes.BIGINT,
      allowNull: false
    },
    device_id: {
      type: DataTypes.STRING(100),
      allowNull: false
    },
    device_name: {
      type: DataTypes.STRING(100)
    },
    system_version: {
      type: DataTypes.STRING(50)
    },
    ip_address: {
      type: DataTypes.STRING(45)
    },
    last_active_at: {
      type: DataTypes.DATE,
      defaultValue: DataTypes.NOW
    },
    refresh_token_hash: {
      type: DataTypes.STRING(255)
    },
    status: {
      type: DataTypes.ENUM('active', 'logged_out'),
      defaultValue: 'active'
    }
  }, {
    tableName: 'login_devices',
    timestamps: true,
    underscored: true,
    indexes: [
      {
        unique: true,
        fields: ['user_id', 'device_id']
      }
    ]
  });

  return LoginDevice;
};
