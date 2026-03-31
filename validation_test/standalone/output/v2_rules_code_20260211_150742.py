# 竞争区间规则引擎 v2.0 — 挖掘输出
# 生成时间: 2026-02-11 15:07:42
# 数据: 15075 场竞争区间, 训练12060/测试3015

# --- 让方不输规则 ---
@rule('WL-H01', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 威立让方变化差<=-0.056 → OOS 100.0%(n=23)')
def _(m):
    return (m['w_r'] > 4.000 and m['wl_hc_diff'] <= -0.056)

@rule('T-H02', 'H', 'A', 'wml',
      '三公司赔率差均值<=2.037 + 澳门受让方>3.650 → OOS 100.0%(n=18)')
def _(m):
    return (m['avg3_spread'] <= 2.037 and m['m_r'] > 3.650)

@rule('WL-H03', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博让方>1.850 → OOS 100.0%(n=15)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_h'] > 1.850)

@rule('WL-H04', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博让方变化>0.049 → OOS 95.8%(n=48)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_hc'] > 0.049)

@rule('T-H05', 'H', 'S', 'wml',
      '立博受让方>3.400 + 威澳返还率差>4.307 → OOS 95.2%(n=62)')
def _(m):
    return (m['l_r'] > 3.400 and m['wm_crr_diff'] > 4.307)

@rule('T-H06', 'H', 'S', 'wml',
      '立博赔率差>1.750 + 威澳返还率差>4.307 → OOS 94.0%(n=50)')
def _(m):
    return (m['l_spread'] > 1.750 and m['wm_crr_diff'] > 4.307)

@rule('D-H07', 'H', 'S', 'wm',
      '澳门受让方>3.150 + 威澳返还率差>4.307 → OOS 93.8%(n=48)')
def _(m):
    return (m['m_r'] > 3.150 and m['wm_crr_diff'] > 4.307)

@rule('T-H08', 'H', 'S', 'wml',
      '澳门赔率差>1.840 + 立博让方变化>0.051 → OOS 93.3%(n=30)')
def _(m):
    return (m['m_spread'] > 1.840 and m['l_hc'] > 0.051)

@rule('WL-H09', 'H', 'S', 'wl',
      '威廉赔率差>2.170 + 立博让方变化>0.049 → OOS 92.7%(n=55)')
def _(m):
    return (m['w_spread'] > 2.170 and m['l_hc'] > 0.049)

@rule('WL-H10', 'H', 'S', 'wl',
      '立博受让方>3.600 + 威廉让方>2.000 → OOS 92.1%(n=38)')
def _(m):
    return (m['l_r'] > 3.600 and m['w_h'] > 2.000)

@rule('D-H11', 'H', 'S', 'wm',
      '澳门赔率差>1.450 + 威澳返还率差>4.307 → OOS 92.1%(n=38)')
def _(m):
    return (m['m_spread'] > 1.450 and m['wm_crr_diff'] > 4.307)

@rule('D-H12', 'H', 'S', 'wm',
      '威廉让方变化<=0.000 + 威廉初盘受让方>4.200 → OOS 92.1%(n=38)')
def _(m):
    return (m['w_hc'] <= 0.000 and m['w_ir'] > 4.200)

@rule('WL-H13', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=-0.093 → OOS 91.9%(n=37)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_rc'] <= -0.093)

@rule('T-H14', 'H', 'S', 'wml',
      '立博让方<=1.800 + 威澳返还率差>4.307 → OOS 91.7%(n=36)')
def _(m):
    return (m['l_h'] <= 1.800 and m['wm_crr_diff'] > 4.307)

@rule('D-H15', 'H', 'S', 'wm',
      '澳门赔率差>1.840 + 威廉让方变化>0.029 → OOS 91.3%(n=46)')
def _(m):
    return (m['m_spread'] > 1.840 and m['w_hc'] > 0.029)

@rule('WL-H16', 'H', 'S', 'wl',
      '立博受让方>3.900 + 立博受让方变化<=-0.054 → OOS 91.2%(n=57)')
def _(m):
    return (m['l_r'] > 3.900 and m['l_rc'] <= -0.054)

@rule('D-H17', 'H', 'S', 'wm',
      '威廉让方<=1.850 + 威廉受让方变化<=-0.133 → OOS 90.9%(n=44)')
def _(m):
    return (m['w_h'] <= 1.850 and m['w_rc'] <= -0.133)

@rule('WL-H18', 'H', 'S', 'wl',
      '立博赔率差>2.100 + 立博让方变化>0.051 → OOS 90.9%(n=44)')
def _(m):
    return (m['l_spread'] > 2.100 and m['l_hc'] > 0.051)

@rule('WL-H19', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博平赔变化>0.033 → OOS 90.7%(n=43)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_dc'] > 0.033)

@rule('T-H20', 'H', 'S', 'wml',
      '三公司受让方均值>3.183 + 威澳返还率差>4.307 → OOS 90.5%(n=74)')
def _(m):
    return (m['avg3_r'] > 3.183 and m['wm_crr_diff'] > 4.307)

@rule('WL-H21', 'H', 'S', 'wl',
      '立博受让方>3.900 + 威廉受让方变化<=-0.093 → OOS 90.5%(n=42)')
def _(m):
    return (m['l_r'] > 3.900 and m['w_rc'] <= -0.093)

@rule('D-H22', 'H', 'S', 'wm',
      '澳门初盘受让方>3.650 + 威澳返还率差>3.690 → OOS 90.5%(n=42)')
def _(m):
    return (m['m_ir'] > 3.650 and m['wm_crr_diff'] > 3.690)

@rule('WL-H23', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=-0.054 → OOS 90.4%(n=52)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_rc'] <= -0.054)

@rule('D-H24', 'H', 'S', 'wm',
      '澳门赔率差>1.840 + 威澳返还率差>3.690 → OOS 90.0%(n=50)')
def _(m):
    return (m['m_spread'] > 1.840 and m['wm_crr_diff'] > 3.690)

@rule('D-H25', 'H', 'A', 'wm',
      '澳门让方<=1.900 + 威澳返还率差>4.307 → OOS 89.8%(n=59)')
def _(m):
    return (m['m_h'] <= 1.900 and m['wm_crr_diff'] > 4.307)

@rule('T-H26', 'H', 'A', 'wml',
      '立博让方<=1.800 + 三公司让方变化均值>0.049 → OOS 89.8%(n=49)')
def _(m):
    return (m['l_h'] <= 1.800 and m['avg3_hc'] > 0.049)

@rule('D-H27', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 威廉让方变化>0.000 → OOS 89.7%(n=68)')
def _(m):
    return (m['m_spread'] > 1.840 and m['w_hc'] > 0.000)

@rule('T-H28', 'H', 'A', 'wml',
      '三公司让方变化均值>0.007 + 澳门赔率差>1.840 → OOS 89.6%(n=67)')
def _(m):
    return (m['avg3_hc'] > 0.007 and m['m_spread'] > 1.840)

@rule('WL-H29', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博平赔变化>0.016 → OOS 89.5%(n=57)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_dc'] > 0.016)

@rule('WL-H30', 'H', 'A', 'wl',
      '立博受让方>3.600 + 立博让方变化>0.049 → OOS 89.1%(n=92)')
def _(m):
    return (m['l_r'] > 3.600 and m['l_hc'] > 0.049)

@rule('T-H31', 'H', 'A', 'wml',
      '立博赔率差>2.100 + 威澳返还率差>3.690 → OOS 88.7%(n=62)')
def _(m):
    return (m['l_spread'] > 2.100 and m['wm_crr_diff'] > 3.690)

@rule('T-H32', 'H', 'A', 'wml',
      '澳门赔率差>1.840 + 立博让方变化>0.000 → OOS 88.7%(n=62)')
def _(m):
    return (m['m_spread'] > 1.840 and m['l_hc'] > 0.000)

@rule('WL-H33', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=0.000 → OOS 88.7%(n=97)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_rc'] <= 0.000)

@rule('WL-H34', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博平赔变化<=-0.015 → OOS 88.6%(n=88)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_dc'] <= -0.015)

@rule('D-H35', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 威廉让方变化>0.029 → OOS 88.2%(n=68)')
def _(m):
    return (m['m_h'] <= 1.800 and m['w_hc'] > 0.029)

@rule('T-H36', 'H', 'A', 'wml',
      '立博让方<=1.800 + 威澳返还率差>3.690 → OOS 88.2%(n=68)')
def _(m):
    return (m['l_h'] <= 1.800 and m['wm_crr_diff'] > 3.690)

@rule('WL-H37', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博让方变化<=0.000 → OOS 88.0%(n=117)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_hc'] <= 0.000)

@rule('WL-H38', 'H', 'A', 'wl',
      '立博赔率差>2.100 + 立博让方变化>0.000 → OOS 88.0%(n=83)')
def _(m):
    return (m['l_spread'] > 2.100 and m['l_hc'] > 0.000)

@rule('D-H39', 'H', 'A', 'wm',
      '威廉让方变化<=0.083 + 威廉初盘受让方>4.200 → OOS 87.9%(n=107)')
def _(m):
    return (m['w_hc'] <= 0.083 and m['w_ir'] > 4.200)

@rule('T-H40', 'H', 'A', 'wml',
      '威廉受让方>4.000 + 三公司让方变化均值>0.007 → OOS 87.8%(n=74)')
def _(m):
    return (m['w_r'] > 4.000 and m['avg3_hc'] > 0.007)

@rule('D-H41', 'H', 'A', 'wm',
      '威廉受让方>4.000 + 威廉让方变化<=0.023 → OOS 87.7%(n=130)')
def _(m):
    return (m['w_r'] > 4.000 and m['w_hc'] <= 0.023)

@rule('T-H42', 'H', 'A', 'wml',
      '澳门赔率差>1.840 + 立博让方变化>-0.022 → OOS 87.6%(n=97)')
def _(m):
    return (m['m_spread'] > 1.840 and m['l_hc'] > -0.022)

@rule('D-H43', 'H', 'A', 'wm',
      '澳门受让方>3.650 + 威澳返还率差>2.910 → OOS 87.6%(n=113)')
def _(m):
    return (m['m_r'] > 3.650 and m['wm_crr_diff'] > 2.910)

@rule('D-H44', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 威廉受让方>4.000 → OOS 87.5%(n=144)')
def _(m):
    return (m['m_h'] <= 1.800 and m['w_r'] > 4.000)

@rule('T-H45', 'H', 'A', 'wml',
      '威廉受让方>4.000 + 三公司让方变化均值>-0.013 → OOS 87.5%(n=96)')
def _(m):
    return (m['w_r'] > 4.000 and m['avg3_hc'] > -0.013)

@rule('D-H46', 'H', 'A', 'wm',
      '威廉赔率差>1.840 + 威廉初盘受让方>4.200 → OOS 87.4%(n=159)')
def _(m):
    return (m['w_spread'] > 1.840 and m['w_ir'] > 4.200)

@rule('WL-H47', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博初盘受让方>3.600 → OOS 87.4%(n=151)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_ir'] > 3.600)

@rule('WL-H48', 'H', 'A', 'wl',
      '立博受让方>3.900 + 威廉初盘受让方>4.200 → OOS 87.3%(n=126)')
def _(m):
    return (m['l_r'] > 3.900 and m['w_ir'] > 4.200)

@rule('D-H49', 'H', 'A', 'wm',
      '威廉受让方>4.000 + 威廉让方变化<=0.083 → OOS 87.2%(n=172)')
def _(m):
    return (m['w_r'] > 4.000 and m['w_hc'] <= 0.083)

@rule('D-H50', 'H', 'A', 'wm',
      '威廉受让方>4.000 + 威廉初盘让方<=1.910 → OOS 87.2%(n=156)')
def _(m):
    return (m['w_r'] > 4.000 and m['w_ih'] <= 1.910)

@rule('D-H51', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 威澳返还率差>3.270 → OOS 87.1%(n=101)')
def _(m):
    return (m['m_spread'] > 1.840 and m['wm_crr_diff'] > 3.270)

@rule('D-H52', 'H', 'A', 'wm',
      '澳门初盘受让方>3.650 + 威廉让方变化>0.029 → OOS 87.1%(n=116)')
def _(m):
    return (m['m_ir'] > 3.650 and m['w_hc'] > 0.029)

@rule('D-H53', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 澳门初盘受让方>3.650 → OOS 87.0%(n=123)')
def _(m):
    return (m['m_spread'] > 1.840 and m['m_ir'] > 3.650)

@rule('D-H54', 'H', 'A', 'wm',
      '威廉受让方变化>-0.094 + 威廉初盘受让方>4.200 → OOS 87.0%(n=92)')
def _(m):
    return (m['w_rc'] > -0.094 and m['w_ir'] > 4.200)

@rule('WL-H55', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博平赔变化>-0.031 → OOS 86.9%(n=130)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_dc'] > -0.031)

@rule('D-H56', 'H', 'A', 'wm',
      '威廉受让方>4.000 + 澳门初盘受让方>3.650 → OOS 86.9%(n=122)')
def _(m):
    return (m['w_r'] > 4.000 and m['m_ir'] > 3.650)

@rule('T-H57', 'H', 'A', 'wml',
      '立博受让方>3.900 + 三公司让方变化均值>0.007 → OOS 86.9%(n=99)')
def _(m):
    return (m['l_r'] > 3.900 and m['avg3_hc'] > 0.007)

@rule('D-H58', 'H', 'A', 'wm',
      '威廉赔率差>2.170 + 威廉初盘受让方>4.200 → OOS 86.7%(n=128)')
def _(m):
    return (m['w_spread'] > 2.170 and m['w_ir'] > 4.200)

@rule('T-H59', 'H', 'A', 'wml',
      '三公司受让方均值>3.857 + 三公司让方变化均值>-0.013 → OOS 86.6%(n=112)')
def _(m):
    return (m['avg3_r'] > 3.857 and m['avg3_hc'] > -0.013)

@rule('T-H60', 'H', 'A', 'wml',
      '立博赔率差>2.100 + 威澳返还率差>3.270 → OOS 86.6%(n=112)')
def _(m):
    return (m['l_spread'] > 2.100 and m['wm_crr_diff'] > 3.270)

@rule('WL-H61', 'H', 'A', 'wl',
      '立博受让方>3.600 + 立博受让方变化<=-0.054 → OOS 86.6%(n=97)')
def _(m):
    return (m['l_r'] > 3.600 and m['l_rc'] <= -0.054)

@rule('D-H62', 'H', 'A', 'wm',
      '威廉赔率差>2.400 → OOS 86.5%(n=171)')
def _(m):
    return (m['w_spread'] > 2.400)

@rule('D-H63', 'H', 'A', 'wm',
      '澳门初盘受让方>3.650 + 威澳返还率差>2.910 → OOS 86.5%(n=111)')
def _(m):
    return (m['m_ir'] > 3.650 and m['wm_crr_diff'] > 2.910)

@rule('T-H64', 'H', 'A', 'wml',
      '澳门初盘受让方>3.650 + 立博让方变化<=0.083 → OOS 86.5%(n=155)')
def _(m):
    return (m['m_ir'] > 3.650 and m['l_hc'] <= 0.083)

@rule('T-H65', 'H', 'A', 'wml',
      '立博受让方>3.600 + 威澳返还率差>3.690 → OOS 86.4%(n=103)')
def _(m):
    return (m['l_r'] > 3.600 and m['wm_crr_diff'] > 3.690)

@rule('D-H66', 'H', 'A', 'wm',
      '澳门初盘受让方>3.650 + 威澳返还率差>2.120 → OOS 86.4%(n=176)')
def _(m):
    return (m['m_ir'] > 3.650 and m['wm_crr_diff'] > 2.120)

@rule('T-H67', 'H', 'A', 'wml',
      '三公司让方变化均值>-0.033 + 澳门赔率差>1.840 → OOS 86.3%(n=117)')
def _(m):
    return (m['avg3_hc'] > -0.033 and m['m_spread'] > 1.840)

@rule('D-H68', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 威廉让方变化>0.000 → OOS 86.3%(n=95)')
def _(m):
    return (m['m_h'] <= 1.800 and m['w_hc'] > 0.000)

@rule('D-H69', 'H', 'A', 'wm',
      '威廉赔率差>2.170 + 威廉受让方变化<=0.018 → OOS 86.3%(n=124)')
def _(m):
    return (m['w_spread'] > 2.170 and m['w_rc'] <= 0.018)

@rule('WL-H70', 'H', 'A', 'wl',
      '立博受让方>3.900 + 威廉让方变化>0.000 → OOS 86.3%(n=102)')
def _(m):
    return (m['l_r'] > 3.900 and m['w_hc'] > 0.000)

@rule('T-H71', 'H', 'A', 'wml',
      '立博受让方>3.900 + 三公司让方变化均值>-0.013 → OOS 86.3%(n=131)')
def _(m):
    return (m['l_r'] > 3.900 and m['avg3_hc'] > -0.013)

@rule('T-H72', 'H', 'A', 'wml',
      '立博受让方>3.900 + 澳门初盘受让方>3.650 → OOS 86.2%(n=145)')
def _(m):
    return (m['l_r'] > 3.900 and m['m_ir'] > 3.650)

@rule('WL-H73', 'H', 'A', 'wl',
      '立博让方<=1.910 + 威廉受让方变化<=-0.030 → OOS 86.1%(n=144)')
def _(m):
    return (m['l_h'] <= 1.910 and m['w_rc'] <= -0.030)

@rule('D-H74', 'H', 'A', 'wm',
      '威廉受让方>4.000 + 威廉受让方变化<=0.056 → OOS 86.1%(n=122)')
def _(m):
    return (m['w_r'] > 4.000 and m['w_rc'] <= 0.056)

@rule('WL-H75', 'H', 'A', 'wl',
      '立博受让方>4.000 → OOS 86.1%(n=165)')
def _(m):
    return (m['l_r'] > 4.000)

@rule('T-H76', 'H', 'A', 'wml',
      '三公司赔率差均值>2.267 → OOS 86.0%(n=150)')
def _(m):
    return (m['avg3_spread'] > 2.267)

@rule('T-H77', 'H', 'A', 'wml',
      '三公司让方变化均值>0.007 + 澳门让方<=1.800 → OOS 86.0%(n=100)')
def _(m):
    return (m['avg3_hc'] > 0.007 and m['m_h'] <= 1.800)

@rule('D-H78', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 威澳返还率差>2.910 → OOS 86.0%(n=157)')
def _(m):
    return (m['m_h'] <= 1.800 and m['wm_crr_diff'] > 2.910)

@rule('D-H79', 'H', 'A', 'wm',
      '威廉让方<=1.850 + 威廉让方变化>0.000 → OOS 85.9%(n=128)')
def _(m):
    return (m['w_h'] <= 1.850 and m['w_hc'] > 0.000)

@rule('T-H80', 'H', 'A', 'wml',
      '三公司赔率差均值>2.038 + 威澳返还率差>2.910 → OOS 85.9%(n=142)')
def _(m):
    return (m['avg3_spread'] > 2.038 and m['wm_crr_diff'] > 2.910)

@rule('T-H81', 'H', 'A', 'wml',
      '立博让方<=1.800 + 威澳返还率差>2.910 → OOS 85.9%(n=142)')
def _(m):
    return (m['l_h'] <= 1.800 and m['wm_crr_diff'] > 2.910)

@rule('D-H82', 'H', 'A', 'wm',
      '威廉赔率差>2.170 + 威廉初盘受让方>3.000 → OOS 85.9%(n=227)')
def _(m):
    return (m['w_spread'] > 2.170 and m['w_ir'] > 3.000)

@rule('D-H83', 'H', 'A', 'wm',
      '澳门让方<=1.750 → OOS 85.9%(n=156)')
def _(m):
    return (m['m_h'] <= 1.750)

@rule('D-H84', 'H', 'A', 'wm',
      '威廉受让方>3.500 + 澳门初盘受让方>3.650 → OOS 85.6%(n=201)')
def _(m):
    return (m['w_r'] > 3.500 and m['m_ir'] > 3.650)

@rule('D-H85', 'H', 'A', 'wm',
      '威廉让方<=1.830 + 威廉受让方变化<=0.018 → OOS 85.5%(n=145)')
def _(m):
    return (m['w_h'] <= 1.830 and m['w_rc'] <= 0.018)

@rule('D-H86', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 澳门初盘受让方>3.650 → OOS 85.5%(n=138)')
def _(m):
    return (m['m_h'] <= 1.800 and m['m_ir'] > 3.650)

@rule('T-H87', 'H', 'A', 'wml',
      '澳门受让方>3.650 + 立博让方变化>-0.045 → OOS 85.5%(n=117)')
def _(m):
    return (m['m_r'] > 3.650 and m['l_hc'] > -0.045)

@rule('D-H88', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 澳门初盘受让方>3.380 → OOS 85.4%(n=151)')
def _(m):
    return (m['m_spread'] > 1.840 and m['m_ir'] > 3.380)

@rule('WL-H89', 'H', 'A', 'wl',
      '立博受让方>3.600 + 威廉初盘让方<=1.800 → OOS 85.4%(n=185)')
def _(m):
    return (m['l_r'] > 3.600 and m['w_ih'] <= 1.800)

@rule('D-H90', 'H', 'A', 'wm',
      '威廉赔率差>2.170 + 威廉初盘让方<=1.800 → OOS 85.4%(n=130)')
def _(m):
    return (m['w_spread'] > 2.170 and m['w_ih'] <= 1.800)

@rule('D-H91', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 澳门受让方>3.650 → OOS 85.4%(n=164)')
def _(m):
    return (m['m_h'] <= 1.800 and m['m_r'] > 3.650)

@rule('WL-H92', 'H', 'A', 'wl',
      '立博赔率差>1.750 + 威廉让方变化>0.000 → OOS 85.4%(n=164)')
def _(m):
    return (m['l_spread'] > 1.750 and m['w_hc'] > 0.000)

@rule('WL-H93', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 立博让方变化>-0.045 → OOS 85.4%(n=123)')
def _(m):
    return (m['w_r'] > 4.000 and m['l_hc'] > -0.045)

@rule('T-H94', 'H', 'A', 'wml',
      '威廉受让方>4.000 + 三公司让方变化均值>-0.033 → OOS 85.3%(n=129)')
def _(m):
    return (m['w_r'] > 4.000 and m['avg3_hc'] > -0.033)

@rule('WL-H95', 'H', 'A', 'wl',
      '立博受让方>3.900 + 立博让方变化>-0.022 → OOS 85.3%(n=129)')
def _(m):
    return (m['l_r'] > 3.900 and m['l_hc'] > -0.022)

@rule('T-H96', 'H', 'A', 'wml',
      '澳门让方<=1.800 + 立博受让方>3.900 → OOS 85.2%(n=176)')
def _(m):
    return (m['m_h'] <= 1.800 and m['l_r'] > 3.900)

@rule('D-H97', 'H', 'A', 'wm',
      '澳门赔率差>2.067 → OOS 85.2%(n=142)')
def _(m):
    return (m['m_spread'] > 2.067)

@rule('WL-H98', 'H', 'A', 'wl',
      '威廉受让方>4.000 + 威立让方变化差>-0.029 → OOS 85.2%(n=155)')
def _(m):
    return (m['w_r'] > 4.000 and m['wl_hc_diff'] > -0.029)

@rule('D-H99', 'H', 'A', 'wm',
      '澳门初盘受让方>3.650 + 威澳返还率差<=5.040 → OOS 85.1%(n=202)')
def _(m):
    return (m['m_ir'] > 3.650 and m['wm_crr_diff'] <= 5.040)

@rule('T-H100', 'H', 'A', 'wml',
      '立博受让方>3.600 + 威澳返还率差>3.270 → OOS 85.0%(n=187)')
def _(m):
    return (m['l_r'] > 3.600 and m['wm_crr_diff'] > 3.270)

@rule('WL-H101', 'H', 'A', 'wl',
      '立博受让方>3.900 + 威廉初盘受让方>3.750 → OOS 85.0%(n=180)')
def _(m):
    return (m['l_r'] > 3.900 and m['w_ir'] > 3.750)

@rule('D-H102', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 威澳返还率差>2.480 → OOS 85.0%(n=160)')
def _(m):
    return (m['m_spread'] > 1.840 and m['wm_crr_diff'] > 2.480)

@rule('D-H103', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 威廉受让方变化<=0.115 → OOS 84.9%(n=152)')
def _(m):
    return (m['m_spread'] > 1.840 and m['w_rc'] <= 0.115)

@rule('T-H104', 'H', 'A', 'wml',
      '澳门初盘受让方>3.650 + 立博让方变化>-0.045 → OOS 84.8%(n=184)')
def _(m):
    return (m['m_ir'] > 3.650 and m['l_hc'] > -0.045)

@rule('T-H105', 'H', 'A', 'wml',
      '三公司赔率差均值>1.343 + 威廉受让方变化<=-0.030 → OOS 84.7%(n=190)')
def _(m):
    return (m['avg3_spread'] > 1.343 and m['w_rc'] <= -0.030)

@rule('D-H106', 'H', 'A', 'wm',
      '澳门让方<=1.900 + 澳门赔率差>1.840 → OOS 84.7%(n=216)')
def _(m):
    return (m['m_h'] <= 1.900 and m['m_spread'] > 1.840)

@rule('D-H107', 'H', 'A', 'wm',
      '澳门受让方>3.650 + 威廉让方变化>-0.071 → OOS 84.7%(n=150)')
def _(m):
    return (m['m_r'] > 3.650 and m['w_hc'] > -0.071)

@rule('D-H108', 'H', 'A', 'wm',
      '威廉让方<=1.850 + 澳门初盘受让方>3.650 → OOS 84.6%(n=162)')
def _(m):
    return (m['w_h'] <= 1.850 and m['m_ir'] > 3.650)

@rule('D-H109', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 威澳返还率差>2.120 → OOS 84.5%(n=213)')
def _(m):
    return (m['m_h'] <= 1.800 and m['wm_crr_diff'] > 2.120)

@rule('T-H110', 'H', 'A', 'wml',
      '三公司受让方均值>3.857 + 立博让方<=1.800 → OOS 84.5%(n=174)')
def _(m):
    return (m['avg3_r'] > 3.857 and m['l_h'] <= 1.800)

@rule('WL-H111', 'H', 'A', 'wl',
      '立博受让方>3.600 + 威廉初盘受让方>3.750 → OOS 84.5%(n=277)')
def _(m):
    return (m['l_r'] > 3.600 and m['w_ir'] > 3.750)

@rule('D-H112', 'H', 'A', 'wm',
      '澳门受让方>3.650 + 威澳返还率差>1.680 → OOS 84.3%(n=191)')
def _(m):
    return (m['m_r'] > 3.650 and m['wm_crr_diff'] > 1.680)

@rule('D-H113', 'H', 'A', 'wm',
      '澳门受让方>3.650 + 威澳返还率差<=5.040 → OOS 84.2%(n=203)')
def _(m):
    return (m['m_r'] > 3.650 and m['wm_crr_diff'] <= 5.040)

@rule('T-H114', 'H', 'A', 'wml',
      '三公司让方变化均值<=0.075 + 澳门受让方>3.650 → OOS 84.1%(n=195)')
def _(m):
    return (m['avg3_hc'] <= 0.075 and m['m_r'] > 3.650)

@rule('D-H115', 'H', 'A', 'wm',
      '澳门让方<=1.800 + 澳门初盘受让方>3.380 → OOS 84.1%(n=176)')
def _(m):
    return (m['m_h'] <= 1.800 and m['m_ir'] > 3.380)

@rule('T-H116', 'H', 'A', 'wml',
      '澳门让方<=1.900 + 三公司受让方均值>3.857 → OOS 84.0%(n=225)')
def _(m):
    return (m['m_h'] <= 1.900 and m['avg3_r'] > 3.857)

@rule('T-H117', 'H', 'A', 'wml',
      '立博赔率差>2.100 + 澳门赔率差>1.840 → OOS 83.9%(n=186)')
def _(m):
    return (m['l_spread'] > 2.100 and m['m_spread'] > 1.840)

@rule('T-H118', 'H', 'A', 'wml',
      '立博受让方>3.600 + 三公司让方变化均值>-0.013 → OOS 83.7%(n=233)')
def _(m):
    return (m['l_r'] > 3.600 and m['avg3_hc'] > -0.013)

@rule('T-H119', 'H', 'A', 'wml',
      '立博受让方>3.600 + 澳门让方<=1.800 → OOS 83.7%(n=233)')
def _(m):
    return (m['l_r'] > 3.600 and m['m_h'] <= 1.800)

@rule('T-H120', 'H', 'A', 'wml',
      '立博让方<=1.800 + 威澳返还率差>2.120 → OOS 83.6%(n=201)')
def _(m):
    return (m['l_h'] <= 1.800 and m['wm_crr_diff'] > 2.120)

@rule('WL-H121', 'H', 'A', 'wl',
      '立博受让方>3.600 + 威廉让方变化>-0.016 → OOS 83.5%(n=231)')
def _(m):
    return (m['l_r'] > 3.600 and m['w_hc'] > -0.016)

@rule('T-H122', 'H', 'A', 'wml',
      '立博赔率差>1.750 + 威澳返还率差>2.910 → OOS 83.5%(n=231)')
def _(m):
    return (m['l_spread'] > 1.750 and m['wm_crr_diff'] > 2.910)

@rule('D-H123', 'H', 'A', 'wm',
      '威廉赔率差>2.000 → OOS 83.1%(n=308)')
def _(m):
    return (m['w_spread'] > 2.000)

@rule('T-H124', 'H', 'A', 'wml',
      '立博受让方>3.600 + 威澳返还率差>2.480 → OOS 82.9%(n=310)')
def _(m):
    return (m['l_r'] > 3.600 and m['wm_crr_diff'] > 2.480)

@rule('WL-H125', 'H', 'A', 'wl',
      '立博受让方>3.800 → OOS 82.8%(n=319)')
def _(m):
    return (m['l_r'] > 3.800)

@rule('T-H126', 'H', 'A', 'wml',
      '立博赔率差>1.750 + 澳门让方<=1.900 → OOS 82.5%(n=355)')
def _(m):
    return (m['l_spread'] > 1.750 and m['m_h'] <= 1.900)

@rule('T-H127', 'H', 'A', 'wml',
      '立博受让方>3.600 + 威澳返还率差>1.680 → OOS 82.5%(n=394)')
def _(m):
    return (m['l_r'] > 3.600 and m['wm_crr_diff'] > 1.680)

@rule('WL-H128', 'H', 'A', 'wl',
      '立博受让方>3.600 + 立博让方变化<=0.083 → OOS 82.2%(n=398)')
def _(m):
    return (m['l_r'] > 3.600 and m['l_hc'] <= 0.083)

@rule('T-H129', 'H', 'A', 'wml',
      '三公司赔率差均值>1.343 + 澳门初盘受让方>3.200 → OOS 82.1%(n=452)')
def _(m):
    return (m['avg3_spread'] > 1.343 and m['m_ir'] > 3.200)


# --- 受让不输规则 ---
@rule('T-R01', 'R', 'A', 'wml',
      '立博让方>2.370 + 三公司让方变化均值<=-0.033 → OOS 93.3%(n=15)')
def _(m):
    return (m['l_h'] > 2.370 and m['avg3_hc'] <= -0.033)

@rule('WL-R02', 'R', 'A', 'wl',
      '立博让方变化>0.136 + 立博初盘让方>2.400 → OOS 87.5%(n=16)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_ih'] > 2.400)

@rule('D-R03', 'R', 'A', 'wm',
      '威廉初盘让方>2.450 + 威廉让方变化>0.132 → OOS 86.4%(n=22)')
def _(m):
    return (m['w_ih'] > 2.450 and m['w_hc'] > 0.132)

@rule('WL-R04', 'R', 'A', 'wl',
      '威廉让方>2.500 + 立博受让方>2.750 → OOS 83.3%(n=18)')
def _(m):
    return (m['w_h'] > 2.500 and m['l_r'] > 2.750)

@rule('T-R05', 'R', 'A', 'wml',
      '立博让方>2.500 + 澳门初盘受让方>2.780 → OOS 81.5%(n=27)')
def _(m):
    return (m['l_h'] > 2.500 and m['m_ir'] > 2.780)

@rule('WL-R06', 'R', 'A', 'wl',
      '立博受让方变化<=-0.054 + 立博初盘让方>2.400 → OOS 81.2%(n=32)')
def _(m):
    return (m['l_rc'] <= -0.054 and m['l_ih'] > 2.400)

@rule('WL-R07', 'R', 'A', 'wl',
      '立博让方变化>0.087 + 立博初盘让方>2.400 → OOS 80.8%(n=26)')
def _(m):
    return (m['l_hc'] > 0.087 and m['l_ih'] > 2.400)

@rule('WL-R08', 'R', 'A', 'wl',
      '立博让方>2.370 + 立博让方变化<=-0.022 → OOS 80.6%(n=36)')
def _(m):
    return (m['l_h'] > 2.370 and m['l_hc'] <= -0.022)

@rule('WL-R09', 'R', 'A', 'wl',
      '威廉让方变化>0.132 + 立博初盘让方>2.400 → OOS 80.6%(n=36)')
def _(m):
    return (m['w_hc'] > 0.132 and m['l_ih'] > 2.400)

@rule('D-R10', 'R', 'A', 'wm',
      '威廉让方变化>0.132 + 威廉初盘返还率>91.420 → OOS 80.6%(n=36)')
def _(m):
    return (m['w_hc'] > 0.132 and m['w_irr'] > 91.420)

@rule('WL-R11', 'R', 'A', 'wl',
      '立博让方变化>0.136 + 立博初盘让方>2.300 → OOS 80.0%(n=25)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_ih'] > 2.300)

@rule('WL-R12', 'R', 'B', 'wl',
      '立博让方变化>0.136 + 立博受让方变化>-0.147 → OOS 77.5%(n=40)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_rc'] > -0.147)

@rule('D-R13', 'R', 'B', 'wm',
      '澳门让方<=2.400 + 威廉让方>2.500 → OOS 77.1%(n=35)')
def _(m):
    return (m['m_h'] <= 2.400 and m['w_h'] > 2.500)

@rule('WL-R14', 'R', 'B', 'wl',
      '立博让方>2.500 + 立博让方变化>0.129 → OOS 76.8%(n=82)')
def _(m):
    return (m['l_h'] > 2.500 and m['l_hc'] > 0.129)

@rule('WL-R15', 'R', 'B', 'wl',
      '立博让方变化>0.049 + 立博初盘让方>2.400 → OOS 76.7%(n=43)')
def _(m):
    return (m['l_hc'] > 0.049 and m['l_ih'] > 2.400)

@rule('T-R16', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 澳门让方<=2.400 → OOS 76.6%(n=47)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['m_h'] <= 2.400)

@rule('WL-R17', 'R', 'B', 'wl',
      '立博让方变化>0.136 + 立博初盘让方>2.100 → OOS 76.0%(n=50)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_ih'] > 2.100)

@rule('WL-R18', 'R', 'B', 'wl',
      '立博让方变化>0.136 + 立博初盘让方>2.200 → OOS 75.0%(n=44)')
def _(m):
    return (m['l_hc'] > 0.136 and m['l_ih'] > 2.200)

@rule('T-R19', 'R', 'B', 'wml',
      '澳门受让方<=2.500 + 威立让方变化差<=-0.014 → OOS 74.6%(n=59)')
def _(m):
    return (m['m_r'] <= 2.500 and m['wl_hc_diff'] <= -0.014)

@rule('T-R20', 'R', 'B', 'wml',
      '三公司受让方均值<=2.587 + 澳门初盘受让方>2.570 → OOS 74.2%(n=66)')
def _(m):
    return (m['avg3_r'] <= 2.587 and m['m_ir'] > 2.570)

@rule('WL-R21', 'R', 'B', 'wl',
      '立博受让方<=2.600 + 威廉初盘返还率<=89.810 → OOS 74.1%(n=85)')
def _(m):
    return (m['l_r'] <= 2.600 and m['w_irr'] <= 89.810)

@rule('WL-R22', 'R', 'B', 'wl',
      '立博受让方<=2.600 + 威廉初盘返还率<=89.410 → OOS 73.8%(n=65)')
def _(m):
    return (m['l_r'] <= 2.600 and m['w_irr'] <= 89.410)

@rule('T-R23', 'R', 'B', 'wml',
      '澳门初盘受让方<=2.680 + 立博让方变化>0.129 → OOS 73.5%(n=68)')
def _(m):
    return (m['m_ir'] <= 2.680 and m['l_hc'] > 0.129)

@rule('D-R24', 'R', 'B', 'wm',
      '澳门受让方<=2.500 + 澳门初盘受让方>2.570 → OOS 73.4%(n=79)')
def _(m):
    return (m['m_r'] <= 2.500 and m['m_ir'] > 2.570)

@rule('WL-R25', 'R', 'B', 'wl',
      '立博赔率差<=0.170 + 威廉初盘返还率<=89.810 → OOS 73.3%(n=86)')
def _(m):
    return (m['l_spread'] <= 0.170 and m['w_irr'] <= 89.810)

@rule('D-R26', 'R', 'B', 'wm',
      '威廉让方>2.500 + 威澳返还率差<=3.280 → OOS 73.1%(n=108)')
def _(m):
    return (m['w_h'] > 2.500 and m['wm_crr_diff'] <= 3.280)

@rule('WL-R27', 'R', 'B', 'wl',
      '立博受让方变化<=-0.054 + 立博初盘让方>2.300 → OOS 72.6%(n=62)')
def _(m):
    return (m['l_rc'] <= -0.054 and m['l_ih'] > 2.300)

@rule('T-R28', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威澳返还率差>2.480 → OOS 72.5%(n=153)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wm_crr_diff'] > 2.480)

@rule('WL-R29', 'R', 'B', 'wl',
      '威廉让方>2.400 + 立博让方变化>0.129 → OOS 72.5%(n=102)')
def _(m):
    return (m['w_h'] > 2.400 and m['l_hc'] > 0.129)

@rule('T-R30', 'R', 'B', 'wml',
      '澳门初盘受让方<=2.910 + 立博让方变化>0.129 → OOS 72.3%(n=101)')
def _(m):
    return (m['m_ir'] <= 2.910 and m['l_hc'] > 0.129)

@rule('D-R31', 'R', 'B', 'wm',
      '威廉赔率差<=0.180 + 威廉初盘返还率<=89.810 → OOS 72.2%(n=79)')
def _(m):
    return (m['w_spread'] <= 0.180 and m['w_irr'] <= 89.810)

@rule('T-R32', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威澳返还率差<=3.280 → OOS 72.1%(n=129)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wm_crr_diff'] <= 3.280)

@rule('T-R33', 'R', 'B', 'wml',
      '立博让方>2.500 + 澳门初盘受让方>2.570 → OOS 72.1%(n=86)')
def _(m):
    return (m['l_h'] > 2.500 and m['m_ir'] > 2.570)

@rule('WL-R34', 'R', 'B', 'wl',
      '立博赔率差<=0.170 + 威廉初盘返还率<=89.410 → OOS 72.1%(n=68)')
def _(m):
    return (m['l_spread'] <= 0.170 and m['w_irr'] <= 89.410)

@rule('WL-R35', 'R', 'B', 'wl',
      '立博让方变化>0.087 + 立博初盘让方>2.200 → OOS 72.0%(n=75)')
def _(m):
    return (m['l_hc'] > 0.087 and m['l_ih'] > 2.200)

@rule('T-R36', 'R', 'B', 'wml',
      '立博让方>2.500 + 三公司让方变化均值>0.115 → OOS 71.8%(n=85)')
def _(m):
    return (m['l_h'] > 2.500 and m['avg3_hc'] > 0.115)

@rule('WL-R37', 'R', 'B', 'wl',
      '威廉让方变化>0.049 + 立博初盘让方>2.400 → OOS 71.6%(n=74)')
def _(m):
    return (m['w_hc'] > 0.049 and m['l_ih'] > 2.400)

@rule('T-R38', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 澳门受让方<=2.500 → OOS 71.6%(n=190)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['m_r'] <= 2.500)

@rule('T-R39', 'R', 'B', 'wml',
      '立博让方>2.500 + 三公司让方变化均值>0.075 → OOS 71.5%(n=123)')
def _(m):
    return (m['l_h'] > 2.500 and m['avg3_hc'] > 0.075)

@rule('T-R40', 'R', 'B', 'wml',
      '澳门受让方<=2.500 + 三公司让方变化均值>0.075 → OOS 71.5%(n=137)')
def _(m):
    return (m['m_r'] <= 2.500 and m['avg3_hc'] > 0.075)

@rule('T-R41', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威澳返还率差>1.680 → OOS 71.3%(n=188)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wm_crr_diff'] > 1.680)

@rule('T-R42', 'R', 'B', 'wml',
      '澳门受让方<=2.500 + 三公司让方变化均值>0.115 → OOS 71.3%(n=94)')
def _(m):
    return (m['m_r'] <= 2.500 and m['avg3_hc'] > 0.115)

@rule('D-R43', 'R', 'B', 'wm',
      '澳门赔率差<=-0.050 → OOS 71.1%(n=149)')
def _(m):
    return (m['m_spread'] <= -0.050)

@rule('D-R44', 'R', 'B', 'wm',
      '威廉让方>2.380 + 威廉受让方Kelly>0.910 → OOS 71.1%(n=97)')
def _(m):
    return (m['w_h'] > 2.380 and m['w_kr'] > 0.910)

@rule('D-R45', 'R', 'B', 'wm',
      '澳门赔率差<=0.150 + 威澳返还率差<=3.270 → OOS 71.1%(n=135)')
def _(m):
    return (m['m_spread'] <= 0.150 and m['wm_crr_diff'] <= 3.270)

@rule('T-R46', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威立让方变化差<=0.007 → OOS 71.0%(n=100)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wl_hc_diff'] <= 0.007)

@rule('T-R47', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 澳门初盘受让方>2.570 → OOS 70.9%(n=86)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['m_ir'] > 2.570)

@rule('T-R48', 'R', 'B', 'wml',
      '立博让方>2.500 + 威澳返还率差>2.480 → OOS 70.9%(n=127)')
def _(m):
    return (m['l_h'] > 2.500 and m['wm_crr_diff'] > 2.480)

@rule('WL-R49', 'R', 'B', 'wl',
      '立博让方>2.450 + 立博让方变化>0.087 → OOS 70.8%(n=89)')
def _(m):
    return (m['l_h'] > 2.450 and m['l_hc'] > 0.087)

@rule('WL-R50', 'R', 'B', 'wl',
      '立博受让方变化<=-0.054 + 立博初盘让方>2.200 → OOS 70.8%(n=106)')
def _(m):
    return (m['l_rc'] <= -0.054 and m['l_ih'] > 2.200)

@rule('D-R51', 'R', 'B', 'wm',
      '威廉受让方<=2.500 → OOS 70.7%(n=150)')
def _(m):
    return (m['w_r'] <= 2.500)

@rule('T-R52', 'R', 'B', 'wml',
      '立博让方>2.500 + 威澳返还率差>1.680 → OOS 70.6%(n=160)')
def _(m):
    return (m['l_h'] > 2.500 and m['wm_crr_diff'] > 1.680)

@rule('T-R53', 'R', 'B', 'wml',
      '立博让方>2.500 + 威澳返还率差<=3.280 → OOS 70.4%(n=115)')
def _(m):
    return (m['l_h'] > 2.500 and m['wm_crr_diff'] <= 3.280)

@rule('D-R54', 'R', 'B', 'wm',
      '威廉让方>2.500 + 澳门初盘受让方>2.570 → OOS 70.3%(n=91)')
def _(m):
    return (m['w_h'] > 2.500 and m['m_ir'] > 2.570)

@rule('D-R55', 'R', 'B', 'wm',
      '威廉让方>2.400 + 威澳返还率差<=3.280 → OOS 70.3%(n=202)')
def _(m):
    return (m['w_h'] > 2.400 and m['wm_crr_diff'] <= 3.280)

@rule('WL-R56', 'R', 'B', 'wl',
      '威廉让方>2.500 + 立博受让方变化<=-0.054 → OOS 70.2%(n=94)')
def _(m):
    return (m['w_h'] > 2.500 and m['l_rc'] <= -0.054)

@rule('WL-R57', 'R', 'B', 'wl',
      '立博让方变化>0.087 + 立博初盘让方>2.100 → OOS 70.1%(n=97)')
def _(m):
    return (m['l_hc'] > 0.087 and m['l_ih'] > 2.100)

@rule('T-R58', 'R', 'B', 'wml',
      '澳门初盘受让方<=2.910 + 三公司让方变化均值>0.115 → OOS 70.1%(n=107)')
def _(m):
    return (m['m_ir'] <= 2.910 and m['avg3_hc'] > 0.115)

@rule('WL-R59', 'R', 'B', 'wl',
      '威廉初盘让方>2.250 + 立博受让方变化<=-0.054 → OOS 70.1%(n=127)')
def _(m):
    return (m['w_ih'] > 2.250 and m['l_rc'] <= -0.054)

@rule('D-R60', 'R', 'B', 'wm',
      '威廉赔率差<=0.130 + 威澳返还率差<=3.690 → OOS 70.0%(n=170)')
def _(m):
    return (m['w_spread'] <= 0.130 and m['wm_crr_diff'] <= 3.690)

@rule('WL-R61', 'R', 'B', 'wl',
      '立博赔率差<=0.700 + 威廉初盘返还率>91.420 → OOS 70.0%(n=110)')
def _(m):
    return (m['l_spread'] <= 0.700 and m['w_irr'] > 91.420)

@rule('D-R62', 'R', 'B', 'wm',
      '威廉让方>2.500 + 威澳返还率差>2.480 → OOS 69.9%(n=146)')
def _(m):
    return (m['w_h'] > 2.500 and m['wm_crr_diff'] > 2.480)

@rule('D-R63', 'R', 'B', 'wm',
      '澳门让方>2.400 + 威澳返还率差<=3.280 → OOS 69.8%(n=126)')
def _(m):
    return (m['m_h'] > 2.400 and m['wm_crr_diff'] <= 3.280)

@rule('T-R64', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威澳返还率差<=5.040 → OOS 69.8%(n=202)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wm_crr_diff'] <= 5.040)

@rule('D-R65', 'R', 'B', 'wm',
      '威廉让方>2.500 + 澳门受让方<=2.500 → OOS 69.8%(n=149)')
def _(m):
    return (m['w_h'] > 2.500 and m['m_r'] <= 2.500)

@rule('D-R66', 'R', 'B', 'wm',
      '澳门赔率差<=0.150 + 威澳返还率差>2.120 → OOS 69.8%(n=192)')
def _(m):
    return (m['m_spread'] <= 0.150 and m['wm_crr_diff'] > 2.120)

@rule('WL-R67', 'R', 'B', 'wl',
      '立博让方>2.450 + 威廉受让方<=2.630 → OOS 69.8%(n=129)')
def _(m):
    return (m['l_h'] > 2.450 and m['w_r'] <= 2.630)

@rule('T-R68', 'R', 'B', 'wml',
      '澳门受让方<=2.500 + 立博让方变化>0.000 → OOS 69.7%(n=188)')
def _(m):
    return (m['m_r'] <= 2.500 and m['l_hc'] > 0.000)

@rule('WL-R69', 'R', 'B', 'wl',
      '立博让方>2.450 + 威廉初盘返还率<=90.930 → OOS 69.7%(n=122)')
def _(m):
    return (m['l_h'] > 2.450 and m['w_irr'] <= 90.930)

@rule('WL-R70', 'R', 'B', 'wl',
      '立博让方变化>-0.048 + 立博初盘让方>2.400 → OOS 69.6%(n=112)')
def _(m):
    return (m['l_hc'] > -0.048 and m['l_ih'] > 2.400)

@rule('T-R71', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 澳门初盘受让方<=2.680 → OOS 69.6%(n=181)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['m_ir'] <= 2.680)

@rule('D-R72', 'R', 'B', 'wm',
      '澳门让方>2.470 → OOS 69.6%(n=148)')
def _(m):
    return (m['m_h'] > 2.470)

@rule('T-R73', 'R', 'B', 'wml',
      '立博赔率差<=0.130 + 三公司让方变化均值>0.075 → OOS 69.6%(n=138)')
def _(m):
    return (m['l_spread'] <= 0.130 and m['avg3_hc'] > 0.075)

@rule('D-R74', 'R', 'B', 'wm',
      '威廉赔率差<=0.130 + 威澳返还率差>2.120 → OOS 69.5%(n=174)')
def _(m):
    return (m['w_spread'] <= 0.130 and m['wm_crr_diff'] > 2.120)

@rule('WL-R75', 'R', 'B', 'wl',
      '立博受让方变化<=-0.054 + 立博初盘让方>2.100 → OOS 69.5%(n=141)')
def _(m):
    return (m['l_rc'] <= -0.054 and m['l_ih'] > 2.100)

@rule('WL-R76', 'R', 'B', 'wl',
      '立博让方变化>0.000 + 立博初盘让方>2.300 → OOS 69.5%(n=118)')
def _(m):
    return (m['l_hc'] > 0.000 and m['l_ih'] > 2.300)

@rule('T-R77', 'R', 'B', 'wml',
      '立博让方>2.500 + 威澳返还率差<=5.040 → OOS 69.4%(n=180)')
def _(m):
    return (m['l_h'] > 2.500 and m['wm_crr_diff'] <= 5.040)

@rule('T-R78', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威立让方变化差>-0.026 → OOS 69.4%(n=180)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wl_hc_diff'] > -0.026)

@rule('D-R79', 'R', 'B', 'wm',
      '威廉赔率差<=-0.050 → OOS 69.4%(n=157)')
def _(m):
    return (m['w_spread'] <= -0.050)

@rule('WL-R80', 'R', 'B', 'wl',
      '立博让方>2.600 → OOS 69.4%(n=147)')
def _(m):
    return (m['l_h'] > 2.600)

@rule('D-R81', 'R', 'B', 'wm',
      '威廉让方>2.500 + 威澳返还率差>1.680 → OOS 69.3%(n=179)')
def _(m):
    return (m['w_h'] > 2.500 and m['wm_crr_diff'] > 1.680)

@rule('WL-R82', 'R', 'B', 'wl',
      '威廉让方>2.400 + 立博受让方<=2.600 → OOS 69.2%(n=182)')
def _(m):
    return (m['w_h'] > 2.400 and m['l_r'] <= 2.600)

@rule('D-R83', 'R', 'B', 'wm',
      '威廉让方>2.630 → OOS 69.2%(n=130)')
def _(m):
    return (m['w_h'] > 2.630)

@rule('WL-R84', 'R', 'B', 'wl',
      '立博让方变化>0.049 + 立博初盘让方>2.100 → OOS 69.0%(n=158)')
def _(m):
    return (m['l_hc'] > 0.049 and m['l_ih'] > 2.100)

@rule('WL-R85', 'R', 'B', 'wl',
      '威廉初盘让方>2.250 + 立博受让方<=2.600 → OOS 69.0%(n=174)')
def _(m):
    return (m['w_ih'] > 2.250 and m['l_r'] <= 2.600)

@rule('D-R86', 'R', 'B', 'wm',
      '澳门让方>2.400 + 威廉受让方<=2.630 → OOS 68.9%(n=151)')
def _(m):
    return (m['m_h'] > 2.400 and m['w_r'] <= 2.630)

@rule('T-R87', 'R', 'B', 'wml',
      '三公司受让方均值<=2.883 + 立博让方变化>0.129 → OOS 68.9%(n=122)')
def _(m):
    return (m['avg3_r'] <= 2.883 and m['l_hc'] > 0.129)

@rule('D-R88', 'R', 'B', 'wm',
      '威廉让方>2.500 + 威澳返还率差<=5.040 → OOS 68.7%(n=179)')
def _(m):
    return (m['w_h'] > 2.500 and m['wm_crr_diff'] <= 5.040)

@rule('WL-R89', 'R', 'B', 'wl',
      '立博让方>2.450 + 威廉让方变化>0.049 → OOS 68.7%(n=131)')
def _(m):
    return (m['l_h'] > 2.450 and m['w_hc'] > 0.049)

@rule('WL-R90', 'R', 'B', 'wl',
      '立博让方变化>-0.048 + 立博初盘让方>2.300 → OOS 68.6%(n=185)')
def _(m):
    return (m['l_hc'] > -0.048 and m['l_ih'] > 2.300)

@rule('WL-R91', 'R', 'B', 'wl',
      '立博让方>2.500 + 威廉让方>2.500 → OOS 68.5%(n=168)')
def _(m):
    return (m['l_h'] > 2.500 and m['w_h'] > 2.500)

@rule('WL-R92', 'R', 'B', 'wl',
      '立博让方>2.500 + 立博受让方<=2.600 → OOS 68.4%(n=133)')
def _(m):
    return (m['l_h'] > 2.500 and m['l_r'] <= 2.600)

@rule('D-R93', 'R', 'B', 'wm',
      '威廉让方>2.500 + 澳门初盘受让方<=2.680 → OOS 68.2%(n=151)')
def _(m):
    return (m['w_h'] > 2.500 and m['m_ir'] <= 2.680)

@rule('WL-R94', 'R', 'B', 'wl',
      '立博让方变化>0.024 + 立博初盘让方>2.200 → OOS 68.2%(n=154)')
def _(m):
    return (m['l_hc'] > 0.024 and m['l_ih'] > 2.200)

@rule('WL-R95', 'R', 'B', 'wl',
      '立博让方>2.450 + 威廉初盘返还率<=91.890 → OOS 68.2%(n=157)')
def _(m):
    return (m['l_h'] > 2.450 and m['w_irr'] <= 91.890)

@rule('D-R96', 'R', 'B', 'wm',
      '澳门赔率差<=0.150 + 威澳返还率差<=4.307 → OOS 68.1%(n=210)')
def _(m):
    return (m['m_spread'] <= 0.150 and m['wm_crr_diff'] <= 4.307)

@rule('D-R97', 'R', 'B', 'wm',
      '威廉赔率差<=0.130 + 威廉让方>2.500 → OOS 68.1%(n=188)')
def _(m):
    return (m['w_spread'] <= 0.130 and m['w_h'] > 2.500)

@rule('T-R98', 'R', 'B', 'wml',
      '三公司受让方均值<=2.587 + 立博让方变化>0.051 → OOS 68.0%(n=147)')
def _(m):
    return (m['avg3_r'] <= 2.587 and m['l_hc'] > 0.051)

@rule('D-R99', 'R', 'B', 'wm',
      '威廉赔率差<=0.130 + 威廉让方>2.400 → OOS 68.0%(n=225)')
def _(m):
    return (m['w_spread'] <= 0.130 and m['w_h'] > 2.400)

@rule('T-R100', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 三公司让方变化均值>0.049 → OOS 68.0%(n=175)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['avg3_hc'] > 0.049)

@rule('D-R101', 'R', 'B', 'wm',
      '威廉让方>2.400 + 澳门初盘受让方<=2.680 → OOS 68.0%(n=231)')
def _(m):
    return (m['w_h'] > 2.400 and m['m_ir'] <= 2.680)

@rule('T-R102', 'R', 'B', 'wml',
      '威廉让方>2.500 + 三公司让方变化均值>0.049 → OOS 67.9%(n=168)')
def _(m):
    return (m['w_h'] > 2.500 and m['avg3_hc'] > 0.049)

@rule('T-R103', 'R', 'B', 'wml',
      '立博让方>2.370 + 威澳返还率差<=2.920 → OOS 67.8%(n=174)')
def _(m):
    return (m['l_h'] > 2.370 and m['wm_crr_diff'] <= 2.920)

@rule('WL-R104', 'R', 'B', 'wl',
      '威廉让方>2.500 + 威立让方变化差>-0.026 → OOS 67.8%(n=174)')
def _(m):
    return (m['w_h'] > 2.500 and m['wl_hc_diff'] > -0.026)

@rule('D-R105', 'R', 'B', 'wm',
      '威廉让方>2.400 + 澳门赔率差<=0.150 → OOS 67.8%(n=236)')
def _(m):
    return (m['w_h'] > 2.400 and m['m_spread'] <= 0.150)

@rule('T-R106', 'R', 'B', 'wml',
      '立博赔率差<=0.130 + 威澳返还率差<=4.310 → OOS 67.7%(n=192)')
def _(m):
    return (m['l_spread'] <= 0.130 and m['wm_crr_diff'] <= 4.310)

@rule('T-R107', 'R', 'B', 'wml',
      '三公司赔率差均值<=0.147 + 威立让方变化差<=0.057 → OOS 67.7%(n=164)')
def _(m):
    return (m['avg3_spread'] <= 0.147 and m['wl_hc_diff'] <= 0.057)

@rule('D-R108', 'R', 'B', 'wm',
      '威廉初盘让方>2.250 + 威廉让方变化>0.023 → OOS 67.6%(n=173)')
def _(m):
    return (m['w_ih'] > 2.250 and m['w_hc'] > 0.023)

@rule('T-R109', 'R', 'B', 'wml',
      '澳门赔率差<=0.150 + 威立让方变化差<=0.057 → OOS 67.6%(n=179)')
def _(m):
    return (m['m_spread'] <= 0.150 and m['wl_hc_diff'] <= 0.057)

@rule('WL-R110', 'R', 'B', 'wl',
      '立博受让方变化<=0.000 + 立博初盘让方>2.200 → OOS 67.1%(n=222)')
def _(m):
    return (m['l_rc'] <= 0.000 and m['l_ih'] > 2.200)

@rule('D-R111', 'R', 'B', 'wm',
      '澳门让方>2.280 + 威廉受让方<=2.630 → OOS 67.0%(n=200)')
def _(m):
    return (m['m_h'] > 2.280 and m['w_r'] <= 2.630)

@rule('D-R112', 'R', 'B', 'wm',
      '威廉让方>2.400 + 威澳返还率差<=4.310 → OOS 66.9%(n=296)')
def _(m):
    return (m['w_h'] > 2.400 and m['wm_crr_diff'] <= 4.310)

@rule('T-R113', 'R', 'B', 'wml',
      '立博让方>2.370 + 威澳返还率差<=3.690 → OOS 66.7%(n=273)')
def _(m):
    return (m['l_h'] > 2.370 and m['wm_crr_diff'] <= 3.690)

@rule('T-R114', 'R', 'B', 'wml',
      '立博赔率差<=0.130 + 三公司让方变化均值>-0.013 → OOS 66.7%(n=216)')
def _(m):
    return (m['l_spread'] <= 0.130 and m['avg3_hc'] > -0.013)

@rule('D-R115', 'R', 'B', 'wm',
      '威廉初盘让方>2.100 + 威廉让方变化>0.023 → OOS 66.5%(n=236)')
def _(m):
    return (m['w_ih'] > 2.100 and m['w_hc'] > 0.023)

@rule('D-R116', 'R', 'B', 'wm',
      '威廉让方>2.400 + 澳门初盘受让方<=3.030 → OOS 66.5%(n=331)')
def _(m):
    return (m['w_h'] > 2.400 and m['m_ir'] <= 3.030)

@rule('WL-R117', 'R', 'B', 'wl',
      '立博受让方变化<=0.000 + 立博初盘让方>2.100 → OOS 65.8%(n=313)')
def _(m):
    return (m['l_rc'] <= 0.000 and m['l_ih'] > 2.100)
