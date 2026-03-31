// utils/storage.js
// 本地存储工具
// 封装 wx.setStorageSync 和 wx.getStorageSync

class Storage {
  /**
   * 设置存储
   * @param {string} key 键名
   * @param {any} value 值
   * @returns {boolean} 是否成功
   */
  set(key, value) {
    try {
      wx.setStorageSync(key, value)
      return true
    } catch (error) {
      console.error('存储失败:', error)
      return false
    }
  }

  /**
   * 获取存储
   * @param {string} key 键名
   * @param {any} defaultValue 默认值
   * @returns {any} 存储的值
   */
  get(key, defaultValue = null) {
    try {
      const value = wx.getStorageSync(key)
      return value !== '' && value !== null && value !== undefined ? value : defaultValue
    } catch (error) {
      console.error('获取存储失败:', error)
      return defaultValue
    }
  }

  /**
   * 删除存储
   * @param {string} key 键名
   * @returns {boolean} 是否成功
   */
  remove(key) {
    try {
      wx.removeStorageSync(key)
      return true
    } catch (error) {
      console.error('删除存储失败:', error)
      return false
    }
  }

  /**
   * 清空所有存储
   * @returns {boolean} 是否成功
   */
  clear() {
    try {
      wx.clearStorageSync()
      return true
    } catch (error) {
      console.error('清空存储失败:', error)
      return false
    }
  }
}

module.exports = new Storage()



