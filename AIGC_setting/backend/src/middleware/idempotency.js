const { IdempotencyKey } = require('../models');

const idempotency = async (req, res, next) => {
  const key = req.header('X-Idempotency-Key');
  if (!key) {
    return next();
  }

  try {
    const existing = await IdempotencyKey.findOne({
      where: { idempotency_key: key }
    });

    if (existing) {
      if (existing.expires_at < new Date()) {
        await existing.destroy();
      } else {
        return res.status(200).json(existing.response_body);
      }
    }

    // Wrap the response.json to store the result
    const originalJson = res.json;
    res.json = function(data) {
      // Store the result only for successful responses (2xx)
      if (res.statusCode >= 200 && res.statusCode < 300) {
        IdempotencyKey.create({
          idempotency_key: key,
          response_body: data,
          expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
        }).catch(err => console.error('Failed to store idempotency key:', err));
      }
      return originalJson.call(this, data);
    };

    next();
  } catch (error) {
    console.error('Idempotency middleware error:', error);
    next();
  }
};

module.exports = idempotency;
