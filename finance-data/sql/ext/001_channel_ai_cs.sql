-- 扩展：智能客服渠道（客服后端调用中台统一携带 X-Channel-Code: AI_CS）
INSERT INTO dim_channel (channel_code, channel_name, channel_type, channel_status, yn, created_at, updated_at)
SELECT 'AI_CS', '智能客服', 'ai_cs', 'active', 1, NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dim_channel WHERE channel_code = 'AI_CS');
