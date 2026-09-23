# KẾ HOẠCH TRIỂN KHAI NCKH
## Knowledge Tracing kết hợp AI Agent cho hệ thống học tập thích ứng

> **Mục tiêu:** xây dựng một pipeline nghiên cứu có thể tái lập, tránh rò rỉ dữ liệu, so sánh các mô hình Knowledge Tracing/ML và khảo sát khả năng dùng Local LLM Agent để chọn bài học tiếp theo.

---

## 1. Phạm vi đã chốt

### Dataset chính
- **ASSISTments 2009–2010 Skill Builder — corrected version**
- Dùng đúng bản corrected:
  - một dòng cho mỗi `student-problem`
  - multi-skill được collapse trong cùng một dòng
- `order_id` được dùng để khôi phục thứ tự tương tác.
- Với MVP, ưu tiên **single-skill interactions**.

### Không làm trong MVP
- DKT
- SAKT
- Transformer KT
- Fine-tune LLM
- RAG
- Multi-agent
- Student simulation
- Real learning gain / RCT
- Dataset thứ hai
- Deploy cloud
- Mobile app

---

# 2. Câu hỏi nghiên cứu

## RQ1 — Knowledge Tracing / Prediction

**Các mô hình khác nhau dự đoán khả năng người học giải đúng bài toán ở lần thử đầu tiên mà không yêu cầu trợ giúp như thế nào?**

So sánh:

1. Global / Problem baseline
2. PFA
3. BKT
4. XGBoost

### Target

`correct`

Cách diễn đạt trong báo cáo:

> Probability of successfully answering the problem on the first attempt without requesting help.

Không diễn đạt target thành:

> Student knows / does not know the skill.

---

## RQ2 — Adaptive Recommendation

**Khi cùng sử dụng một student state, cùng knowledge graph và cùng candidate set, Local LLM Agent đưa ra lựa chọn bài học như thế nào so với deterministic policy?**

So sánh:

### B+
`KT + Knowledge Graph + deterministic rule`

### Agent
`KT + Knowledge Graph + Local LLM`

RQ2 là **exploratory study**.

Không claim:

> Agent làm người học tiến bộ hơn.

---

# 3. Cấu trúc project

```text
adaptive-learning-nckh/
│
├── data/
│   ├── raw/
│   │   └── assistments_2009_2010_skill_builder_corrected.csv
│   └── processed/
│
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_baseline_pfa.ipynb
│   ├── 04_bkt.ipynb
│   ├── 05_xgboost.ipynb
│   ├── 06_calibration.ipynb
│   └── 07_rq2_analysis.ipynb
│
├── src/
│   ├── preprocessing/
│   ├── models/
│   ├── knowledge_graph/
│   ├── recommender/
│   ├── agent/
│   └── utils/
│
├── artifacts/
│   ├── models/
│   ├── plots/
│   ├── tables/
│   └── logs/
│
├── evaluation/
│   ├── scenarios/
│   ├── human_eval/
│   └── results/
│
├── app/
│   └── streamlit_app.py
│
├── reports/
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

# 4. Môi trường chạy local

## Python

Khuyến nghị:

```text
Python 3.11
```

## Packages chính

```bash
pip install pandas numpy scipy scikit-learn xgboost matplotlib jupyter pyBKT networkx pydantic joblib streamlit
```

Nếu dùng Ollama qua Python:

```bash
pip install ollama
```

## `requirements.txt` tối thiểu

```text
pandas
numpy
scipy
scikit-learn
xgboost
matplotlib
jupyter
pyBKT
networkx
pydantic
joblib
streamlit
ollama
```

---

# 5. Git / bảo vệ dữ liệu

`.gitignore`

```gitignore
data/
artifacts/models/
*.csv
*.parquet
*.pkl
*.joblib
.ipynb_checkpoints/
__pycache__/
.env
```

Không push raw dataset lên GitHub.

---

# 6. Phase 1 — EDA

## Mục tiêu

Hiểu đúng file thật trước khi train.

## Việc phải kiểm tra

### 6.1 Kích thước dữ liệu

```python
df.shape
```

### 6.2 Danh sách cột

```python
df.columns.tolist()
```

### 6.3 Kiểu dữ liệu

```python
df.info()
```

### 6.4 Missing values

```python
df.isna().sum().sort_values(ascending=False)
```

### 6.5 Số lượng thực thể

Kiểm tra:

```text
number of students
number of problems
number of skills
number of interactions
```

### 6.6 Phân phối target

```python
df["correct"].value_counts(dropna=False)
df["correct"].value_counts(normalize=True)
```

### 6.7 Kiểm tra `order_id`

- Có missing không?
- Có duplicate bất thường không?
- Với vài student, sort theo `order_id` và xem trajectory.

### 6.8 Kiểm tra multi-skill

Bản corrected collapse multi-skill thành một dòng.

Cần xác định cách encode thực tế trong:

```text
skill_name
skill_id
```

Không đoán trước separator nếu chưa xem file.

### 6.9 Kiểm tra duplicate

Phân biệt:

- duplicate thực sự
- cùng problem xuất hiện lại hợp lệ
- multi-skill đã collapse

---

# 7. Phase 2 — Cleaning và preprocessing

## 7.1 Lọc missing skill

Trước khi bỏ:

```python
missing_skill_rate = df["skill_id"].isna().mean()
```

Ghi lại tỷ lệ.

Sau đó mới lọc.

---

## 7.2 Single-skill subset

MVP dùng single-skill để:

- đơn giản hóa BKT
- đơn giản hóa PFA
- tránh ambiguity khi update nhiều skill
- dễ giải thích trước hội đồng

Phải báo cáo:

```text
Original interactions = N
Single-skill interactions = M
Retained rate = M / N
```

---

## 7.3 Sort interactions

```python
df = df.sort_values(["user_id", "order_id"])
```

---

# 8. Leakage checklist — BẮT BUỘC

Nếu dự đoán:

```text
correct[t]
```

thì feature chỉ được lấy từ:

```text
interaction < t
```

## Không dùng trực tiếp tại thời điểm `t`

Ví dụ:

```text
hint_count[t]
attempt_count[t]
first_action[t]
bottom_hint[t]
```

nếu những biến này được sinh ra trong chính interaction hiện tại.

## Chỉ dùng lịch sử

Ví dụ:

```text
prior_success_skill
prior_failure_skill
prior_skill_accuracy
prior_overall_accuracy
prior_hint_count
history_length
```

---

# 9. Feature engineering an toàn

## 9.1 Prior skill success

```python
df["prior_skill_success"] = (
    df.groupby(["user_id", "skill_id"])["correct"]
      .transform(lambda x: x.shift().fillna(0).cumsum())
)
```

## 9.2 Prior skill count

```python
df["prior_skill_count"] = (
    df.groupby(["user_id", "skill_id"]).cumcount()
)
```

## 9.3 Prior skill failure

```python
df["prior_skill_failure"] = (
    df["prior_skill_count"] - df["prior_skill_success"]
)
```

## 9.4 Prior overall accuracy

Phải shift trước khi expanding.

Không dùng current interaction.

---

# 10. Problem difficulty

## Sai

```text
Toàn dataset
→ tính mean correct theo problem
→ dùng cho train/test
```

Vì test label đã ảnh hưởng feature.

## Đúng

```text
TRAIN ONLY
→ tính problem success/difficulty
→ map sang validation/test
```

Problem chưa từng thấy trong train:

```text
fallback = global train mean
```

---

# 11. Data split

## Protocol chính

**Student-disjoint split**

Ví dụ:

```text
70% students → Train
15% students → Validation
15% students → Test
```

Kiểm tra bắt buộc:

```text
Train user_id ∩ Validation user_id = ∅
Train user_id ∩ Test user_id = ∅
Validation user_id ∩ Test user_id = ∅
```

## Warm-up cho test student

Ví dụ:

```text
t1–t5  → build history
t6+    → evaluation
```

MVP:

```text
minimum history = 5 interactions
```

Nếu còn thời gian, sensitivity check:

```text
3 / 5 / 10 interactions
```

---

# 12. Model 0 — Baseline

## Global baseline

```text
P(success) = mean(correct) trên TRAIN
```

## Problem baseline

```text
P(success | problem) = mean(correct) của problem trên TRAIN
```

Problem unseen:

```text
global train mean
```

Đây là baseline tối thiểu để biết model phức tạp có thực sự hữu ích không.

---

# 13. Model 1 — PFA

Core variables:

```text
skill
prior successes
prior failures
```

Output:

```text
P(success next interaction)
```

Ưu điểm:
- nhẹ
- dễ giải thích
- baseline Knowledge Tracing hợp lý

---

# 14. Model 2 — BKT

Theo từng skill.

Parameters:

```text
P(L0)
P(T)
P(G)
P(S)
```

Sau từng interaction:

```text
observe result
→ update posterior mastery
```

Lưu student state để dùng sau cho phần recommendation.

---

# 15. Model 3 — XGBoost

Candidate features:

```text
skill_id
problem_id
prior_skill_success
prior_skill_failure
prior_skill_accuracy
prior_overall_accuracy
history_length
problem_difficulty_train_only
```

Có thể thêm feature sau nếu chứng minh không leakage.

Không thêm feature chỉ để tăng AUC.

---

# 16. Hyperparameter tuning

Không cần search quá lớn.

## XGBoost

Chỉ tune vài tham số:

```text
n_estimators
max_depth
learning_rate
subsample
colsample_bytree
min_child_weight
```

Dùng validation set.

Không tune trên test set.

## PFA/BKT

Giữ cấu hình đơn giản và tái lập được.

---

# 17. Metrics cho RQ1

Metric chính:

```text
ROC-AUC
Brier Score
Log Loss
Calibration Curve
```

Accuracy/F1 chỉ là phụ nếu cần.

## Vì sao cần calibration?

Agent/policy phía sau dùng:

```text
P(success)
```

nên xác suất phải có ý nghĩa, không chỉ ranking tốt.

---

# 18. Bảng kết quả RQ1

Template:

| Model | ROC-AUC ↑ | Brier ↓ | Log Loss ↓ |
|---|---:|---:|---:|
| Global |  |  |  |
| Problem |  |  |  |
| PFA |  |  |  |
| BKT |  |  |  |
| XGBoost |  |  |  |

Không giả định XGBoost sẽ thắng.

---

# 19. Reproducibility

Set random seed:

```python
RANDOM_STATE = 42
```

Ghi lại:

```text
Python version
package versions
split seed
model parameters
number of rows after filtering
number of students
number of skills
```

Lưu model:

```text
artifacts/models/
```

Lưu metrics:

```text
artifacts/tables/
```

Lưu plots:

```text
artifacts/plots/
```

---

# 20. Điều kiện để kết thúc RQ1

RQ1 chỉ coi là hoàn thành khi có:

- dataset clean
- split không overlap student
- leakage checklist pass
- Global baseline
- Problem baseline
- PFA
- BKT
- XGBoost
- ROC-AUC
- Brier
- Log Loss
- Calibration curves
- bảng so sánh cuối cùng
- model/student state dùng cho RQ2

---

# 21. Phase 3 — Student Knowledge State

Không tự động chia:

```text
Weak / Medium / Mastered
```

bằng ngưỡng tùy tiện.

Ưu tiên dùng probability trực tiếp:

```json
{
  "skill_A": 0.28,
  "skill_B": 0.54,
  "skill_C": 0.82
}
```

Nếu cần threshold thì chọn bằng validation set và mô tả rõ.

---

# 22. Knowledge Graph

Dùng:

```text
NetworkX
```

hoặc JSON.

MVP chỉ cần:

```text
10–30 skills
```

Ví dụ:

```text
Fraction
   ↓
Ratio
   ↓
Equation
```

Quan hệ prerequisite phải:

- có nguồn nếu có thể
- hoặc ghi rõ là giả định thiết kế của prototype

---

# 23. Candidate Generator

Tạo một danh sách nhỏ bài phù hợp.

Ví dụ:

```text
Q12
Q16
Q35
Q43
Q52
```

Cả B+ và Agent phải nhận **đúng cùng candidate set**.

Đây là điều kiện để RQ2 công bằng.

---

# 24. System B+

Không dùng LLM.

Pipeline:

```text
student state
↓
find weakest valid skill
↓
check prerequisite
↓
select suitable difficulty
↓
choose one candidate problem
```

Deterministic.

---

# 25. Local Agent

Stack:

```text
Python
Ollama
Pydantic
```

Không fine-tune.

Không RAG.

Không multi-agent.

## Input

```json
{
  "student_state": {},
  "prerequisites": {},
  "candidate_problems": []
}
```

## Output bắt buộc

```json
{
  "problem_id": 123,
  "reason": "..."
}
```

Nếu `problem_id` không nằm trong candidate set:

```text
INVALID
```

---

# 26. RQ2 Evaluation

## Quy mô

```text
50–100 scenarios
```

Mỗi scenario:

```text
3 Agent runs
```

Ví dụ:

```text
50 scenarios × 3 = 150 decisions
```

## Metrics tự động

```text
Valid JSON rate
Valid candidate selection rate
Prerequisite violation rate
Difficulty violation rate
Consistency across runs
Latency
Token count (nếu lấy được)
```

---

# 27. Human evaluation

Nếu có nguồn lực:

```text
20–30 cases
2 raters
```

Blind order.

Rubric 3 tiêu chí:

```text
1. Skill phù hợp
2. Difficulty phù hợp
3. Lý do recommendation hợp lý
```

Không gọi người chấm là "expert" nếu không đúng chuyên môn.

Không claim significance nếu sample quá nhỏ.

---

# 28. Demo

Dùng:

```text
Streamlit
```

MVP:

```text
Student ID
Knowledge state
Recommended problem
Reason
```

Không cần:

```text
Login
Admin
Cloud
Mobile
```

---

# 29. Timeline 12 tuần

| Tuần | Công việc | Deliverable |
|---|---|---|
| 1 | EDA, schema, target, order_id, missing, multi-skill | `01_eda.ipynb` |
| 2 | Cleaning, single-skill, split, leakage-safe features | processed dataset |
| 3 | Global/Problem baseline + PFA | baseline results |
| 4 | Hoàn thiện PFA + BKT | BKT results |
| 5 | XGBoost + tuning nhỏ | XGBoost results |
| 6 | AUC, Brier, Log Loss, calibration | **RQ1 complete** |
| 7 | Student state + Knowledge Graph | graph + states |
| 8 | Candidate generator + B+ | B+ complete |
| 9 | Ollama + Agent MVP | local Agent |
| 10 | Agent experiments | raw RQ2 logs |
| 11 | Human evaluation + analysis | RQ2 results |
| 12 | Streamlit + report + presentation | final demo |

---

# 30. Phân bổ công sức

```text
Data + preprocessing    25%
KT / ML                 30%
Evaluation              20%
Agent                   15%
Demo                    10%
```

Nếu chậm tiến độ:

**Cắt UI trước, không cắt leakage check hoặc evaluation.**

---

# 31. Checklist trước khi bắt đầu train

## Data

- [ ] Đúng corrected file
- [ ] Đã backup raw file
- [ ] Đã đọc schema thật
- [ ] Đã kiểm tra missing
- [ ] Đã kiểm tra `order_id`
- [ ] Đã xác định multi-skill encoding
- [ ] Đã lọc single-skill
- [ ] Đã ghi số dòng bị loại
- [ ] Target semantics đúng

## Split

- [ ] Student-disjoint
- [ ] Không overlap user
- [ ] Random seed cố định
- [ ] Warm-up rule được ghi rõ

## Leakage

- [ ] Không dùng current hint
- [ ] Không dùng current attempt count
- [ ] Không dùng future interactions
- [ ] Problem difficulty chỉ fit trên train
- [ ] Encoders/statistics fit trên train
- [ ] Validation/test không ảnh hưởng preprocessing statistics

## Training

- [ ] Baseline chạy trước
- [ ] PFA
- [ ] BKT
- [ ] XGBoost
- [ ] Hyperparameter chỉ tune bằng validation
- [ ] Test chỉ chạy khi pipeline đã khóa

## Evaluation

- [ ] ROC-AUC
- [ ] Brier
- [ ] Log Loss
- [ ] Calibration curve
- [ ] Lưu params
- [ ] Lưu seed
- [ ] Lưu kết quả

---

# 32. Nguyên tắc dừng scope

Không thêm mô hình chỉ vì:

> "model này mới hơn"

Chỉ thêm khi:

1. RQ1 đã hoàn thành.
2. RQ2 đã có B+ và Agent chạy được.
3. Evaluation đã xong.
4. Còn thời gian thực sự.

Ưu tiên:

```text
Correct methodology
>
More models
```

---

# 33. Việc phải làm ngay bây giờ

1. Tải ASSISTments corrected CSV.
2. Đặt file vào:

```text
data/raw/
```

3. Tạo virtual environment.
4. Cài requirements.
5. Tạo `01_eda.ipynb`.
6. Chạy:

```python
import pandas as pd

df = pd.read_csv("data/raw/<ten_file>.csv")

print("Shape:", df.shape)
print(df.columns.tolist())
display(df.head(10))
df.info()
```

7. Lưu output.
8. Chỉ sau khi hiểu schema thật mới viết preprocessing.

---

# 34. Definition of Done

Đề tài MVP được xem là hoàn thành khi:

- [ ] ASSIST09 đã được xử lý đúng
- [ ] Không có leakage đã biết
- [ ] 4 nhóm mô hình/baseline đã chạy
- [ ] Có calibration
- [ ] RQ1 có bảng kết quả hoàn chỉnh
- [ ] Có student knowledge state
- [ ] Có knowledge graph nhỏ
- [ ] B+ và Agent dùng cùng candidate set
- [ ] RQ2 có offline evaluation
- [ ] Có limitations rõ ràng
- [ ] Có Streamlit demo tối thiểu
- [ ] Có code + seed + config đủ để tái lập

---

## Ghi chú quan trọng

Phần **train thực sự** của đề tài nằm ở PFA/BKT/XGBoost hoặc quá trình fit tham số tương ứng. Local LLM Agent **không được train/fine-tune trong MVP**; nó chỉ được cấu hình và đánh giá như một policy lựa chọn bài học.
