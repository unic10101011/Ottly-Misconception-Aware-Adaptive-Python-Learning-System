const bcrypt = require('bcrypt');

module.exports = (sequelize, DataTypes) => {
  const User = sequelize.define('User', {
    id: {
      type: DataTypes.BIGINT,
      primaryKey: true,
      autoIncrement: true
    },
    username: {
      type: DataTypes.STRING(50),
      unique: true,
      allowNull: false
    },
    password_hash: {
      type: DataTypes.STRING(255),
      allowNull: false
    },
    phone: {
      type: DataTypes.STRING(20),
      unique: true
    },
    email: {
      type: DataTypes.STRING(100),
      unique: true
    },
    avatar_url: {
      type: DataTypes.STRING(255)
    },
    theme_preference: {
      type: DataTypes.STRING(20),
      defaultValue: 'system'
    },
    lang_preference: {
      type: DataTypes.STRING(10),
      defaultValue: 'zh-CN'
    }
  }, {
    tableName: 'users',
    hooks: {
      beforeSave: async (user) => {
        if (user.changed('password_hash')) {
          const salt = await bcrypt.genSalt(12);
          user.password_hash = await bcrypt.hash(user.password_hash, salt);
        }
      }
    }
  });

  User.prototype.comparePassword = async function(password) {
    return await bcrypt.compare(password, this.password_hash);
  };

  return User;
};
