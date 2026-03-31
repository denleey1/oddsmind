"""
概率校准模块
提供Isotonic、Platt等后验校准方法，提升预测概率的可靠性
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import logging

logger = logging.getLogger(__name__)


class ProbabilityCalibrator:
    """概率校准器基类"""
    
    def __init__(self, method: str = 'isotonic'):
        """
        Args:
            method: 校准方法 'isotonic', 'platt', 'beta', 'identity'
        """
        self.method = method
        self.calibrator = None
        self.is_fitted = False
    
    def fit(self, y_pred: np.ndarray, y_true: np.ndarray):
        """
        拟合校准器
        
        Args:
            y_pred: 预测概率 (N,)
            y_true: 真实标签 0/1 (N,)
        """
        if len(y_pred) < 10:
            logger.warning(f"样本量过小({len(y_pred)})，跳过校准")
            self.method = 'identity'
            self.is_fitted = True
            return
        
        if self.method == 'isotonic':
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(y_pred, y_true)
        
        elif self.method == 'platt':
            # Platt scaling: logistic regression
            self.calibrator = LogisticRegression()
            X = y_pred.reshape(-1, 1)
            self.calibrator.fit(X, y_true)
        
        elif self.method == 'beta':
            # Beta calibration (简化版)
            self._fit_beta(y_pred, y_true)
        
        elif self.method == 'identity':
            pass  # 不校准
        
        else:
            raise ValueError(f"Unknown calibration method: {self.method}")
        
        self.is_fitted = True
    
    def transform(self, y_pred: np.ndarray) -> np.ndarray:
        """
        应用校准
        
        Args:
            y_pred: 原始预测概率
        
        Returns:
            校准后的概率
        """
        if not self.is_fitted:
            logger.warning("校准器未拟合，返回原始概率")
            return y_pred
        
        if self.method == 'isotonic':
            return self.calibrator.predict(y_pred)
        
        elif self.method == 'platt':
            X = y_pred.reshape(-1, 1)
            return self.calibrator.predict_proba(X)[:, 1]
        
        elif self.method == 'beta':
            return self._transform_beta(y_pred)
        
        else:  # identity
            return y_pred
    
    def _fit_beta(self, y_pred: np.ndarray, y_true: np.ndarray):
        """Beta校准拟合"""
        from scipy.special import logit, expit
        
        # 避免0/1
        y_pred_safe = np.clip(y_pred, 1e-6, 1-1e-6)
        
        def loss(params):
            a, b, c = params
            calibrated = expit(a + b * logit(y_pred_safe) + c * logit(y_pred_safe)**2)
            return -np.sum(y_true * np.log(calibrated + 1e-10) + 
                          (1-y_true) * np.log(1 - calibrated + 1e-10))
        
        result = minimize(loss, x0=[0, 1, 0], method='L-BFGS-B')
        self.beta_params = result.x
    
    def _transform_beta(self, y_pred: np.ndarray) -> np.ndarray:
        """Beta校准变换"""
        from scipy.special import logit, expit
        
        y_pred_safe = np.clip(y_pred, 1e-6, 1-1e-6)
        a, b, c = self.beta_params
        calibrated = expit(a + b * logit(y_pred_safe) + c * logit(y_pred_safe)**2)
        return np.clip(calibrated, 0, 1)


class MultiClassCalibrator:
    """多分类校准器 (用于三分类: S≤2, S=3, S≥4)"""
    
    def __init__(self, method: str = 'isotonic'):
        self.method = method
        self.calibrators = {}
        self.is_fitted = False
    
    def fit(self, y_pred: np.ndarray, y_true: np.ndarray, classes: List[str] = None):
        """
        拟合多分类校准
        
        Args:
            y_pred: 预测概率矩阵 (N, K)
            y_true: 真实类别索引 (N,) 或 one-hot (N, K)
            classes: 类别名称列表
        """
        if classes is None:
            classes = [f"class_{i}" for i in range(y_pred.shape[1])]
        
        # 转换y_true为索引
        if len(y_true.shape) > 1:
            y_true_idx = np.argmax(y_true, axis=1)
        else:
            y_true_idx = y_true.astype(int)
        
        # 为每个类别拟合一个校准器
        for i, cls in enumerate(classes):
            y_binary = (y_true_idx == i).astype(int)
            y_pred_cls = y_pred[:, i]
            
            cal = ProbabilityCalibrator(method=self.method)
            cal.fit(y_pred_cls, y_binary)
            self.calibrators[cls] = cal
        
        self.classes = classes
        self.is_fitted = True
    
    def transform(self, y_pred: np.ndarray) -> np.ndarray:
        """
        应用多分类校准
        
        Args:
            y_pred: 原始预测概率 (N, K)
        
        Returns:
            校准后的概率 (N, K)，已归一化
        """
        if not self.is_fitted:
            return y_pred
        
        calibrated = np.zeros_like(y_pred)
        
        for i, cls in enumerate(self.classes):
            calibrated[:, i] = self.calibrators[cls].transform(y_pred[:, i])
        
        # 归一化
        row_sums = calibrated.sum(axis=1, keepdims=True)
        calibrated = calibrated / (row_sums + 1e-10)
        
        return calibrated


def calculate_calibration_metrics(y_pred: np.ndarray, y_true: np.ndarray, n_bins: int = 10) -> Dict:
    """
    计算校准指标
    
    Returns:
        包含ECE, MCE, Brier score等指标的字典
    """
    # Expected Calibration Error (ECE)
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    
    ece = 0.0
    mce = 0.0
    bin_data = []
    
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (y_pred > bin_lower) & (y_pred <= bin_upper)
        prop_in_bin = in_bin.mean()
        
        if prop_in_bin > 0:
            accuracy_in_bin = y_true[in_bin].mean()
            avg_confidence_in_bin = y_pred[in_bin].mean()
            
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin
            mce = max(mce, np.abs(avg_confidence_in_bin - accuracy_in_bin))
            
            bin_data.append({
                'bin_lower': bin_lower,
                'bin_upper': bin_upper,
                'confidence': avg_confidence_in_bin,
                'accuracy': accuracy_in_bin,
                'count': in_bin.sum()
            })
    
    # Brier Score
    brier = np.mean((y_pred - y_true) ** 2)
    
    # Log Loss
    y_pred_safe = np.clip(y_pred, 1e-10, 1 - 1e-10)
    log_loss = -np.mean(y_true * np.log(y_pred_safe) + (1 - y_true) * np.log(1 - y_pred_safe))
    
    return {
        'ece': round(ece, 6),
        'mce': round(mce, 6),
        'brier': round(brier, 6),
        'log_loss': round(log_loss, 6),
        'bin_data': bin_data
    }


def dirichlet_calibration(probs: np.ndarray, labels: np.ndarray, reg: float = 1e-3) -> Tuple[np.ndarray, Dict]:
    """
    Dirichlet校准 (多分类联合校准)
    
    Args:
        probs: 预测概率 (N, K)
        labels: 真实标签 (N,) 或 one-hot (N, K)
        reg: 正则化强度
    
    Returns:
        (校准参数, 信息字典)
    """
    from scipy.special import softmax
    
    K = probs.shape[1]
    
    # 转换为索引
    if len(labels.shape) > 1:
        labels_idx = np.argmax(labels, axis=1)
    else:
        labels_idx = labels.astype(int)
    
    # 初始化权重矩阵和偏置
    W = np.eye(K)
    b = np.zeros(K)
    
    def loss(params):
        W_flat = params[:K*K].reshape(K, K)
        b = params[K*K:]
        
        # 线性变换 + softmax
        logits = probs @ W_flat.T + b
        calibrated = softmax(logits, axis=1)
        
        # 交叉熵损失 + L2正则
        nll = -np.sum(np.log(calibrated[np.arange(len(labels_idx)), labels_idx] + 1e-10))
        reg_term = reg * (np.sum(W_flat ** 2) + np.sum(b ** 2))
        
        return nll + reg_term
    
    # 优化
    params_init = np.concatenate([W.flatten(), b])
    result = minimize(loss, params_init, method='L-BFGS-B')
    
    W_opt = result.x[:K*K].reshape(K, K)
    b_opt = result.x[K*K:]
    
    return {'W': W_opt, 'b': b_opt}, {'loss': result.fun, 'success': result.success}


if __name__ == "__main__":
    print("=== 概率校准模块测试 ===\n")
    
    # 生成测试数据 (过度自信的预测)
    np.random.seed(42)
    n_samples = 500
    
    # 模拟过度自信的预测概率
    y_true = np.random.binomial(1, 0.5, n_samples)
    y_pred_raw = np.random.beta(2, 2, n_samples)
    y_pred = 0.3 + 0.4 * y_pred_raw  # 压缩到0.3-0.7
    
    # 让预测更极端
    y_pred = np.where(y_pred > 0.5, y_pred * 1.3, y_pred * 0.7)
    y_pred = np.clip(y_pred, 0.01, 0.99)
    
    print("测试1: 单分类校准 (Isotonic vs Platt)\n")
    
    # 分割数据
    split = int(0.7 * n_samples)
    y_pred_train, y_pred_test = y_pred[:split], y_pred[split:]
    y_true_train, y_true_test = y_true[:split], y_true[split:]
    
    # 原始指标
    metrics_raw = calculate_calibration_metrics(y_pred_test, y_true_test)
    print(f"原始预测: ECE={metrics_raw['ece']:.4f}, Brier={metrics_raw['brier']:.4f}, LogLoss={metrics_raw['log_loss']:.4f}")
    
    # Isotonic校准
    cal_iso = ProbabilityCalibrator(method='isotonic')
    cal_iso.fit(y_pred_train, y_true_train)
    y_pred_iso = cal_iso.transform(y_pred_test)
    metrics_iso = calculate_calibration_metrics(y_pred_iso, y_true_test)
    print(f"Isotonic:  ECE={metrics_iso['ece']:.4f}, Brier={metrics_iso['brier']:.4f}, LogLoss={metrics_iso['log_loss']:.4f}")
    
    # Platt校准
    cal_platt = ProbabilityCalibrator(method='platt')
    cal_platt.fit(y_pred_train, y_true_train)
    y_pred_platt = cal_platt.transform(y_pred_test)
    metrics_platt = calculate_calibration_metrics(y_pred_platt, y_true_test)
    print(f"Platt:     ECE={metrics_platt['ece']:.4f}, Brier={metrics_platt['brier']:.4f}, LogLoss={metrics_platt['log_loss']:.4f}")
    
    # 测试2: 三分类校准
    print("\n测试2: 三分类校准 (S≤2, S=3, S≥4)\n")
    
    # 生成三分类数据
    y_true_3class = np.random.choice([0, 1, 2], n_samples, p=[0.4, 0.3, 0.3])
    y_pred_3class = np.random.dirichlet([2, 2, 2], n_samples)
    
    # 使预测偏向某些类别
    y_pred_3class[:, 0] *= 1.2
    y_pred_3class = y_pred_3class / y_pred_3class.sum(axis=1, keepdims=True)
    
    train_3, test_3 = split, n_samples
    
    cal_multi = MultiClassCalibrator(method='isotonic')
    cal_multi.fit(y_pred_3class[:train_3], y_true_3class[:train_3], classes=['S≤2', 'S=3', 'S≥4'])
    
    y_pred_3class_cal = cal_multi.transform(y_pred_3class[train_3:test_3])
    
    print(f"原始三分类平均概率: {y_pred_3class[train_3:test_3].mean(axis=0)}")
    print(f"校准后平均概率:     {y_pred_3class_cal.mean(axis=0)}")
    print(f"真实分布:           {np.bincount(y_true_3class[train_3:test_3], minlength=3) / len(y_true_3class[train_3:test_3])}")







