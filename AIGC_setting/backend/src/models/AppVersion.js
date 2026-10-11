module.exports = (sequelize, DataTypes) => {
  const AppVersion = sequelize.define('AppVersion', {
    id: {
      type: DataTypes.BIGINT,
      primaryKey: true,
      autoIncrement: true
    },
    version_code: {
      type: DataTypes.INTEGER,
      allowNull: false
    },
    version_name: {
      type: DataTypes.STRING(20),
      allowNull: false
    },
    update_log: {
      type: DataTypes.TEXT
    },
    is_force_update: {
      type: DataTypes.BOOLEAN,
      defaultValue: false
    },
    grayscale_ratio: {
      type: DataTypes.DECIMAL(5, 2),
      defaultValue: 100.00
    },
    download_url: {
      type: DataTypes.STRING(255)
    },
    platform: {
      type: DataTypes.ENUM('android', 'ios'),
      allowNull: false
    }
  }, {
    tableName: 'app_versions',
    timestamps: true,
    underscored: true
  });

  return AppVersion;
};
