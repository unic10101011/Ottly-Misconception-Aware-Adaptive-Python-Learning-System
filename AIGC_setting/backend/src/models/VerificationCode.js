module.exports = (sequelize, DataTypes) => {
  const VerificationCode = sequelize.define('VerificationCode', {
    id: {
      type: DataTypes.BIGINT,
      primaryKey: true,
      autoIncrement: true
    },
    target: {
      type: DataTypes.STRING(100),
      allowNull: false
    },
    code: {
      type: DataTypes.STRING(10),
      allowNull: false
    },
    type: {
      type: DataTypes.ENUM('bind', 'unbind', 'reset_password'),
      allowNull: false
    },
    expires_at: {
      type: DataTypes.DATE,
      allowNull: false
    },
    failed_attempts: {
      type: DataTypes.INTEGER,
      defaultValue: 0
    },
    cooldown_until: {
      type: DataTypes.DATE
    }
  }, {
    tableName: 'verification_codes',
    timestamps: true,
    underscored: true
  });

  return VerificationCode;
};
