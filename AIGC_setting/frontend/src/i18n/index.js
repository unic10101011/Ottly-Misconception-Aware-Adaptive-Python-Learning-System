import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import AsyncStorage from '@react-native-async-storage/async-storage';

const resources = {
  'zh-CN': {
    translation: {
      'settings': '设置',
      'account_security': '账号与安全',
      'notifications': '通知设置',
      'clear_cache': '清除缓存',
      'dark_mode': '夜间模式',
      'language': '语言选择',
      'about_us': '关于我们',
      'phone_email_binding': '手机号/邮箱绑定',
      'change_password': '修改密码',
      'login_devices': '最近登录设备',
      'system_notifications': '系统消息',
      'activity_notifications': '活动消息',
      'ai_reply_notifications': 'AI 回复',
      'cache_images': '图片缓存',
      'cache_voice': '语音缓存',
      'temp_files': '临时文件',
      'follow_system': '跟随系统',
      'forced_on': '强制开启',
      'forced_off': '强制关闭',
      'check_updates': '检查更新',
      'user_agreement': '用户协议',
      'privacy_policy': '隐私政策',
      'current_version': '当前版本',
      'releasing_cache': '正在释放...',
      'cache_released': '已释放 {{size}} MB',
      'password_strength': '密码强度',
      'logout_device': '登出设备',
      'confirm_logout': '确认登出该设备吗？',
      'cancel': '取消',
      'confirm': '确认',
      'bind': '绑定',
      'unbind': '换绑',
      'verification_code': '验证码',
      'get_code': '获取验证码',
      'password': '密码',
    }
  },
  'en-US': {
    translation: {
      'settings': 'Settings',
      'account_security': 'Account & Security',
      'notifications': 'Notifications',
      'clear_cache': 'Clear Cache',
      'dark_mode': 'Dark Mode',
      'language': 'Language',
      'about_us': 'About Us',
      'phone_email_binding': 'Phone/Email Binding',
      'change_password': 'Change Password',
      'login_devices': 'Recent Login Devices',
      'system_notifications': 'System Notifications',
      'activity_notifications': 'Activity Notifications',
      'ai_reply_notifications': 'AI Reply',
      'cache_images': 'Image Cache',
      'cache_voice': 'Voice Cache',
      'temp_files': 'Temporary Files',
      'follow_system': 'Follow System',
      'forced_on': 'Always On',
      'forced_off': 'Always Off',
      'check_updates': 'Check Updates',
      'user_agreement': 'User Agreement',
      'privacy_policy': 'Privacy Policy',
      'current_version': 'Current Version',
      'releasing_cache': 'Releasing...',
      'cache_released': 'Released {{size}} MB',
      'password_strength': 'Password Strength',
      'logout_device': 'Logout Device',
      'confirm_logout': 'Confirm logout this device?',
      'cancel': 'Cancel',
      'confirm': 'Confirm',
      'bind': 'Bind',
      'unbind': 'Change Binding',
      'verification_code': 'Verification Code',
      'get_code': 'Get Code',
      'password': 'Password',
    }
  }
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: 'zh-CN',
    fallbackLng: 'en-US',
    interpolation: {
      escapeValue: false
    }
  });

export const loadLanguage = async () => {
  const lang = await AsyncStorage.getItem('lang_preference');
  if (lang) {
    i18n.changeLanguage(lang);
  }
};

export default i18n;
