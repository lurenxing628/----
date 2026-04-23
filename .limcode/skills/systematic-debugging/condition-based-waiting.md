# 条件等待

不要写固定睡眠去赌时序，例如：

```python
import time

time.sleep(3)
```

这类写法的问题是：

- 慢的时候不够
- 快的时候浪费
- 在不同机器和不同数据量下不稳定

## 正确做法

改成“等条件成立，或超时失败”。

```python
import time


def wait_until(predicate, timeout=5.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False
```

## 使用原则

- 条件要具体、可观察
- 超时后要报清楚错，不要无声失败
- 条件等待适用于：后台任务完成、文件出现、状态切换、页面异步加载完成

## 红线

- 不能把固定等待和条件等待混着乱用
- 不能为了“稳一点”无限加大等待时间
- 不能超时后继续假装成功