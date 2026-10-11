module.exports = (sequelize, DataTypes) => {
  const IdempotencyKey = sequelize.define('IdempotencyKey', {
    id: {
      type: DataTypes.BIGINT,
      primaryKey: true,
      autoIncrement: true
    },
    idempotency_key: {
      type: DataTypes.STRING(100),
      unique: true,
      allowNull: false
    },
    response_body: {
      type: DataTypes.JSON
    },
    expires_at: {
      type: DataTypes.DATE,
      allowNull: false
    }
  }, {
    tableName: 'idempotency_keys',
    timestamps: true,
    underscored: true
  });

  return IdempotencyKey;
};
