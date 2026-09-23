# KẾ HOẠCH TRIỂN KHAI NCKH — V3
## Knowledge Tracing kết hợp Local LLM Agent cho hệ thống học tập thích ứng

> **Trạng thái:** đủ để bắt đầu EDA ngay.  
> **Fit/tuning RQ1 bắt đầu sau khi hoàn thành EDA và khóa protocol RQ1. Cấu hình cuối của RQ1 và RQ2 được khóa riêng trước khi mở tập test tương ứng.**

---

# 1. Mục tiêu và phạm vi

Đề tài gồm hai phần:

## RQ1 — Knowledge Tracing / Prediction

So sánh khả năng dự đoán:

> **xác suất người học giải đúng bài toán ở lần thử đầu tiên mà không yêu cầu trợ giúp**

giữa:

1. Global baseline
2. Problem baseline
3. PFA
4. BKT
5. XGBoost

Không bổ sung DKT, SAKT, Transformer KT trong MVP.

---

## RQ2 — Adaptive Recommendation

So sánh trong cùng điều kiện đầu vào:

```text
B+ = BKT state + Knowledge Graph + deterministic policy
vs
Agent = BKT state + Knowledge Graph + Local LLM policy
```

Cả hai phải nhận:

```text
same student state
same prerequisite graph
same candidate set
```

RQ2 là **exploratory study**.

Không claim:

- learning gain
- causal educational benefit
- Agent giúp người học tiến bộ hơn

---

# 2. Dataset

## Dataset chính

**ASSISTments 2009–2010 Skill Builder — corrected version**

Quy ước:

- `order_id`: dùng làm thứ tự tương tác
- `correct`: first-attempt success / không yêu cầu trợ giúp
- corrected file: one row per student-problem
- multi-skill được collapse trong cùng một dòng

MVP ưu tiên:

```text
single-skill interactions
```

Phải báo cáo:

```text
original rows
rows sau missing-skill filtering
single-skill rows
retained rate
students
problems
skills
```

---

# 3. Research Gap — phát biểu tạm thời

Không tuyên bố:

> chưa ai từng kết hợp Knowledge Tracing và LLM.

Khoảng trống được đặt hẹp:

> Trong một thiết lập học tập thích ứng có kiểm soát và tài nguyên hạn chế, chưa rõ một Local LLM nhỏ có đem lại lợi ích thực nghiệm rõ ràng so với deterministic recommendation policy khi cả hai nhận cùng student knowledge state, cùng prerequisite graph và cùng candidate set.

Đây mới là **working research gap**.

Trước khi viết báo cáo chính thức phải xác minh bằng literature review.

---

# 4. Literature Review Table bắt buộc

Tạo bảng khoảng 5–10 nghiên cứu liên quan gần nhất:

| Paper | Student state | Recommendation policy | Deterministic baseline? | LLM/Agent? | Evaluation | Limitation relevant to us |
|---|---|---|---|---|---|---|
| Paper 1 |  |  |  |  |  |  |
| Paper 2 |  |  |  |  |  |  |
| Paper 3 |  |  |  |  |  |  |

Mục tiêu không phải chứng minh “chưa ai làm”.

Mục tiêu là xác định:

> nghiên cứu này kiểm tra thêm điều gì trong một setting cụ thể.

---

# 5. Expected Contributions

## Contribution 1 — RQ1

Một pipeline KT/ML:

- student-disjoint
- leakage-aware
- sequential evaluation
- probability calibration analysis
- student-level uncertainty estimation

trên ASSIST09 corrected single-skill subset.

## Contribution 2 — RQ2

Comparison có kiểm soát:

```text
deterministic policy
vs
Local LLM policy
```

với cùng:

```text
state
graph
candidate set
```

## Contribution 3 — Resource-constrained evidence

Đánh giá Local LLM về:

- output validity
- constraint adherence
- stability
- latency
- rationale quality

trong môi trường zero-cost/local.

## Nếu Agent không hơn B+

Cách diễn giải mặc định:

> Trong phạm vi thử nghiệm, chưa ghi nhận bằng chứng rõ ràng rằng Agent cải thiện các tiêu chí đã định so với B+.

Không tự động viết:

> hai hệ thống tương đương.

Muốn kết luận tương đương phải có thiết kế/phân tích dành riêng cho equivalence.

---

# 6. Cấu trúc project

```text
adaptive-learning-nckh/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_baselines_pfa.ipynb
│   ├── 04_bkt.ipynb
│   ├── 05_xgboost.ipynb
│   ├── 06_rq1_evaluation.ipynb
│   └── 07_rq2_analysis.ipynb
│
├── src/
│   ├── preprocessing/
│   ├── models/
│   ├── evaluation/
│   ├── knowledge_graph/
│   ├── recommender/
│   └── agent/
│
├── artifacts/
│   ├── models/
│   ├── plots/
│   ├── tables/
│   └── logs/
│
├── evaluation/
│   ├── rq2_validation_scenarios/
│   ├── rq2_test_scenarios/
│   └── human_eval/
│
├── app/
├── reports/
├── requirements.txt
├── .gitignore
└── README.md
```

---

# 7. EDA — làm ngay

EDA chưa cần khóa toàn bộ modeling choices.

Có thể kiểm tra schema và tính toàn vẹn trên toàn file. Sau khi chia student-disjoint, dùng TRAIN để quyết định minimum skill support, dạng PFA, cách xử lý sparse skills và các lựa chọn dựa trên phân phối dữ liệu. Dùng VALIDATION cho tuning theo protocol đã định; không dùng TEST để điều chỉnh thiết kế. Các thống kê mô tả TEST phục vụ báo cáo không được dùng ngược lại để thay đổi pipeline.

Kiểm tra:

```text
df.shape
df.columns
df.info()
missing values
target distribution
n_students
n_problems
n_skills
n_interactions
order_id
duplicates
multi-skill encoding
skill_id / skill_name consistency
problem frequency
skill frequency
interactions per student
```

Đặc biệt cần phân phối:

```text
interactions per student
interactions per skill
interactions per problem
```

vì các kết quả này quyết định:

- minimum skill support
- sparse/unseen handling
- warm-up feasibility
- PFA/BKT fitting strategy

---

# 8. Cleaning

## Missing skill

Đo tỷ lệ trước khi loại.

## Multi-skill

MVP dùng single-skill subset.

Không mặc định separator trước khi xem schema thực tế.

## Thứ tự

Sau cleaning:

```python
df = df.sort_values(["user_id", "order_id"])
```

### Warm-up được tính trên:

> **chuỗi interaction sau toàn bộ cleaning/filtering dùng cho modeling**

không tính trên raw sequence.

---

# 9. Student split

Primary protocol:

```text
70% students → train
15% students → validation
15% students → test
```

Seed cố định.

Bắt buộc:

```python
assert train_users.isdisjoint(val_users)
assert train_users.isdisjoint(test_users)
assert val_users.isdisjoint(test_users)
```

---

# 10. Warm-up / Eligible evaluation rows

Giá trị mặc định dự kiến:

```text
warm-up = 5 cleaned interactions
```

Student có:

```text
<= 5 eligible interactions
```

thì:

- không có scored rows trong validation/test
- vẫn phải báo cáo số student bị loại khỏi evaluation
- quyết định có dùng các interaction đó trong train hay không phải khóa trong Configuration Lock sau EDA

Mọi model phải được chấm trên:

```text
same evaluation rows
same students
same warm-up rule
same target
```

---

# 11. Leakage Policy

Nếu predict:

```text
correct[t]
```

thì không dùng feature phát sinh tại interaction `t`, ví dụ:

```text
hint_count[t]
attempt_count[t]
bottom_hint[t]
first_action[t]
```

Chỉ dùng:

```text
history < t
```

Ví dụ:

```text
prior_success
prior_failure
prior_skill_accuracy
prior_overall_accuracy
history_length
prior_hint_count
```

---

# 12. Sequential Evaluation

Sau warm-up:

```text
state/history before t
↓
predict y[t]
↓
save prediction
↓
observe true y[t]
↓
update student history/state
↓
move to t+1
```

Không được:

```text
observe y[t]
↓
update
↓
predict y[t]
```

Trong validation/test:

```text
global model parameters = fixed
```

Chỉ student history/state được cập nhật.

---

# 13. Problem Difficulty Feature

## Validation / Test

Fit statistics từ toàn bộ TRAIN rồi transform validation/test.

## TRAIN

Không dùng mean của toàn bộ train rồi gán ngược lại chính train rows.

Phải dùng:

```text
GroupKFold / cross-fitting by user_id
```

Mỗi fold:

```text
fit problem statistics trên allowed folds
↓
transform held-out fold
```

### Smoothing

Trong mỗi fit partition:

```text
smoothed_p =
(n_problem * p_problem + alpha * p_global)
/
(n_problem + alpha)
```

Quan trọng:

> `p_problem`, `p_global`, `n_problem` đều chỉ được tính từ các fold được phép fit.

Unseen problem fallback:

```text
p_global của fit partition tương ứng
```

`alpha` khóa trước test.

---

# 14. Encoding Policy

Phải khóa sau EDA.

Các nguyên tắc bắt buộc:

- không coi numeric ID như ordinal quantity nếu bản chất chỉ là category
- mọi encoder/statistic fit bằng train hợp lệ
- validation/test không ảnh hưởng mapping

## PFA

Skill được biểu diễn dưới dạng categorical effect / skill coefficient.

## XGBoost

Phương án cuối phải được ghi rõ trong Configuration Lock, ví dụ:

```text
skill_id: categorical
problem_id: categorical hoặc không dùng
```

Không thay encoding sau khi nhìn test result.

---

# 15. Baselines

## Global baseline

```text
P(success) = train global mean
```

## Problem baseline

```text
P(success | problem)
```

fit từ train labels.

Problem unseen:

```text
train global mean
```

Problem baseline là một model baseline độc lập nên không cần OOF theo cách target-derived feature của XGBoost cần.

---

# 16. PFA

## Preferred form

PFA chuẩn hơn:

```text
logit P(correct_ijt)
=
β_j
+ γ_j * prior_success_ijt
+ ρ_j * prior_failure_ijt
```

Trong đó:

```text
β_j = skill intercept
γ_j = success coefficient của skill j
ρ_j = failure coefficient của skill j
```

## Nếu dữ liệu quá sparse

Có thể dùng biến thể đơn giản:

```text
logit P(correct_ijt)
=
β_j
+ γ * prior_success_ijt
+ ρ * prior_failure_ijt
```

Nhưng phải gọi đúng:

> **PFA variant with shared history coefficients**

Không trình bày như PFA skill-specific đầy đủ.

### Quyết định cuối

Chốt sau EDA dựa trên support per skill, trước test.

### Regularization

Dùng regularization, ví dụ L2.

Hyperparameter chỉ chọn bằng train/validation.

---

# 17. BKT

Per-skill latent state:

```text
P(L0)
P(T)
P(G)
P(S)
```

## Prediction cho RQ1

Trước khi quan sát label:

```text
P(correct_t)
=
P(L_t) * (1 - P(S))
+
(1 - P(L_t)) * P(G)
```

Sau đó mới:

```text
observe y[t]
↓
Bayesian update
↓
learning transition
↓
state t+1
```

Không dùng posterior sau khi nhìn `y[t]` để chấm chính `y[t]`.

### BKT fitting choices cần khóa sau EDA

- fit per skill hay pooled/partially pooled
- initialization
- parameter bounds
- minimum train interactions per skill
- unseen skill fallback

Không chọn bằng test.

---

# 18. XGBoost

Candidate features:

```text
prior_skill_success
prior_skill_failure
prior_skill_accuracy
prior_overall_accuracy
history_length
cross-fitted problem difficulty
skill categorical feature
optional problem categorical feature
```

Feature list cuối phải khóa trước test.

Không thêm feature chỉ vì test metric thấp.

---

# 19. P(success) vs P(mastery)

Hai đại lượng khác nhau.

## P(success)

```text
P(correct on a particular interaction/problem)
```

## P(mastery)

```text
latent skill knowledge estimate
```

Không mặc định:

```text
P(success) = P(mastery)
```

---

# 20. Student State cho RQ2

MVP dùng:

> **BKT latent mastery**

Ví dụ:

```json
{
  "state_type": "BKT_p_mastery",
  "skills": {
    "skill_A": 0.28,
    "skill_B": 0.54,
    "skill_C": 0.82
  }
}
```

Phải mô tả:

> đây là model-based latent estimate, không phải ground-truth mastery.

Model thắng RQ1 không bắt buộc phải là nguồn state cho RQ2.

---

# 21. Metrics RQ1

Chốt trước khi mở test.

Đề xuất mặc định:

```text
Primary probability metric: Brier Score
Secondary discrimination metric: ROC-AUC
Additional metric: Log Loss
```

Calibration curve dùng để **đánh giá calibration**.

Nếu fit calibrator thì chỉ fit trên validation/calibration data, không dùng test.

---

# 22. Uncertainty

Dùng:

```text
paired bootstrap by student
```

Không bootstrap từng interaction độc lập.

Mỗi bootstrap iteration:

```text
sample test students with replacement
↓
take all scored interactions of sampled students
↓
compute Model A metric
↓
compute Model B metric
↓
store difference
```

Báo cáo:

```text
point estimate
95% bootstrap CI
```

---

# 23. Model Selection

Không dùng test để:

- chọn model
- chọn threshold
- chọn smoothing alpha
- chọn BKT policy
- chọn XGBoost features
- chọn calibration method
- chọn prompt
- chọn LLM
- sửa B+

Test chỉ dùng sau khi config đã khóa.

---

# 24. Knowledge Graph

MVP:

```text
10–30 skills
```

Dùng NetworkX hoặc JSON.

Prerequisite edge phải:

- có nguồn nếu có thể
- hoặc ghi rõ là prototype assumption

---

# 25. Candidate Generator

Candidate generator không được làm bài toán quá trivial.

Mọi candidate phải hợp lệ ở mức tối thiểu, nhưng vẫn nên khác nhau về:

- target skill
- prerequisite readiness
- difficulty fit
- remediation vs progression
- challenge level

Không loại hết mọi khác biệt trước khi B+/Agent được chọn.

---

# 26. B+ Deterministic Policy

Phải khóa trước test.

Ví dụ decision hierarchy:

1. prerequisite-relevant weak skill
2. target difficulty fit
3. remediation/progression rule
4. support/count tie-break
5. `problem_id` deterministic tie-break

Không đổi rule sau khi xem Agent test output.

---

# 27. RQ2 phải tách Validation và Test

## Validation scenarios

Dùng để:

- phát triển prompt
- chọn local LLM configuration
- sửa JSON schema
- sửa B+
- sửa rubric
- chọn timeout/retry rule
- kiểm tra candidate generator

Có thể xem output nhiều lần.

## Test scenarios

Chỉ dùng sau khi:

```text
prompt locked
LLM locked
B+ locked
rubric locked
candidate generator locked
timeout/retry locked
```

Không sửa hệ thống sau khi bắt đầu xem test results.

---

# 28. Scenario Sampling

Validation và test scenario phải tách theo protocol.

Có thể sample từ student states tương ứng với:

```text
validation students
test students
```

Không dùng cùng scenario cho development và final evaluation.

Sampling phải cố định bằng seed.

Mặc định MVP: lấy một state snapshot cho mỗi student được chọn, chỉ dùng lịch sử đến thời điểm snapshot; không dùng nhãn tương lai để tạo state hoặc chọn candidate. Validation/test scenarios lấy từ các nhóm student tương ứng, không overlap student.

Nếu lấy nhiều snapshot của cùng student, phải ghi rõ và phân tích độ bất định theo cụm student, giữ các scenario và repeated runs của student đó cùng nhau. Không coi các snapshot này là những mẫu độc lập.

Có thể stratify theo:

- low / medium / high mastery
- simple / branching prerequisite structure
- short / long history

---

# 29. Agent

Stack:

```text
Python
Ollama
Pydantic
```

Không fine-tune.

Không RAG.

Không multi-agent.

Output tối thiểu:

```json
{
  "problem_id": 123,
  "reason": "..."
}
```

Nếu problem ngoài candidate set:

```text
INVALID
```

---

# 30. Agent Runtime Protocol

Chốt trước test:

- model name
- quantization
- temperature
- context size
- prompt
- schema
- timeout
- maximum repair attempts

Nếu dùng repair:

```text
first-pass valid rate
final valid rate after repair
```

đều phải báo cáo.

---

# 31. Repeated Runs

Ví dụ:

```text
50 test scenarios × 3 runs
```

Nếu mỗi scenario thuộc một student khác nhau, số đơn vị đánh giá độc lập ở cấp student là:

```text
50 scenarios
```

Ba lần chạy chỉ dùng để đo:

- consistency
- stability
- variance

Không coi là 150 independent samples. Nếu có nhiều scenario cùng student, số student mới là số cụm độc lập dùng cho uncertainty analysis; báo cáo cả số student, scenario và run.

---

# 32. Human Evaluation

Nếu làm được:

```text
20–30 test scenarios
2 raters
```

Blind system identity.

Rubric độc lập với B+:

1. phù hợp với student state
2. phù hợp prerequisite structure
3. difficulty/recommendation hợp lý
4. rationale nhất quán với input

Có thể gộp thành 3 tiêu chí để giảm workload.

Không gọi rater là “expert” nếu không đúng.

---

# 33. RQ2 Metrics

Có thể gồm:

```text
valid JSON rate
valid candidate rate
constraint adherence
recommendation consistency
latency
timeout/error rate
rationale rubric score
```

Chỉ dùng metric nào không bị candidate generator quyết định sẵn.

---

# 34. Hardware Smoke Test — làm sớm

Tuần 1–2:

1. Cài Ollama
2. Chọn một model local nhỏ
3. Tạo 5 synthetic JSON scenarios
4. Test structured output
5. Đo:
   - latency
   - RAM/VRAM
   - valid JSON rate
   - candidate validity

Pilot này chỉ kiểm tra feasibility.

Không dùng làm kết quả RQ2.

---

# 35. Configuration Lock

Duy trì **một bảng cấu hình duy nhất**, nhưng khóa theo ba mốc. Không yêu cầu hoàn thành RQ2 trước khi train RQ1.

- **Mốc A — trước fit/tuning RQ1:** khóa protocol dữ liệu, đánh giá và phạm vi tuning. Những tham số cần lựa chọn bằng validation chưa cần có giá trị cuối.
- **Mốc B — trước mở TEST RQ1:** khóa toàn bộ cấu hình RQ1 cuối cùng đã chọn bằng train/validation.
- **Mốc C — trước mở TEST RQ2:** khóa toàn bộ policy và protocol RQ2 sau development trên validation scenarios.

| Hạng mục | Lựa chọn cuối / phạm vi được phép | Lý do | Thời điểm khóa |
|---|---|---|---|
| Random seed và split ratio |  |  | A |
| Single-skill / cleaning rule |  |  | A |
| Warm-up length và student ≤ warm-up handling |  |  | A |
| Evaluation mask rule |  |  | A |
| Primary RQ1 metric và model-selection rule |  |  | A |
| OOF folds và cross-fitting policy |  |  | A |
| PFA form | skill-specific / shared variant |  | A |
| BKT fit strategy, bounds, initialization |  |  | A |
| BKT minimum train support và unseen skill handling |  |  | A |
| XGBoost encoding và candidate features |  |  | A |
| Search space / tuning budget cho các model và smoothing |  |  | A |
| Calibration development protocol | none / validation protocol |  | A |
| Problem smoothing alpha đã chọn |  |  | B |
| PFA regularization đã chọn |  |  | B |
| BKT cấu hình cuối |  |  | B |
| XGBoost hyperparameters / final features |  |  | B |
| Final fitting policy | Giữ model fit trên train / protocol refit đã định |  | B |
| Calibration method và fitted calibrator nếu có |  |  | B |
| Bootstrap iterations, seed và CI protocol |  |  | B |
| BKT state definition / checkpoint dùng cho RQ2 |  |  | C |
| Knowledge graph version |  |  | C |
| Candidate generator và B+ rule |  |  | C |
| RQ2 validation / test scenario counts |  |  | C |
| Scenario sampling seed, eligibility và snapshot rule |  |  | C |
| Local LLM / model version / quantization |  |  | C |
| Temperature, seed policy và context size |  |  | C |
| Prompt / output schema version |  |  | C |
| Timeout / retry / repair rule |  |  | C |
| RQ2 metrics và repeated-run aggregation |  |  | C |
| Human-eval rubric và sampling nếu thực hiện |  |  | C |

Sau mỗi mốc khóa, lưu config có version và ngày khóa. Không thay lựa chọn dựa trên test result. Thay đổi protocol trong development phải ghi lý do và hoàn tất trước khi mở test tương ứng.

Nếu bắt buộc sửa vì bug sau khi mở test:

- ghi lại thay đổi và giải thích lý do;
- rerun toàn bộ test protocol liên quan;
- công khai việc test đã được xem; rerun không biến test thành một tập chưa từng được xem.

## Hồ sơ tái lập

Lưu cùng mỗi experiment:

- nguồn tải, tên phiên bản và SHA-256 của raw CSV;
- Python version, package versions và dependency lock/snapshot;
- danh sách student IDs của từng split, lưu cục bộ cùng dữ liệu;
- config version, code commit nếu dùng Git, seeds và evaluation row IDs;
- model checkpoint và preprocessing artifacts;
- với RQ2: model version/digest, quantization, prompt/schema, graph/candidate versions, hardware và runtime version;
- predictions, metrics và logs đủ để tái tạo bảng kết quả.

Không đưa raw dataset hoặc danh sách student IDs lên repository công khai.

---

# 36. Training / Test Gates

## Gate A — bắt đầu fit/tuning RQ1

```text
DATA CHECK PASS
+
SPLIT CHECK PASS
+
LEAKAGE CHECK PASS
+
CROSS-FIT CHECK PASS
+
SEQUENTIAL EVALUATION TEST PASS
+
CONFIGURATION LOCK A COMPLETE
```

Gate này cho phép fit và tuning trên TRAIN/VALIDATION; không yêu cầu cấu hình RQ2 hoàn thành và không cho phép mở TEST.

## Gate B — đánh giá cuối RQ1

```text
RQ1 DEVELOPMENT COMPLETE
+
CONFIGURATION LOCK B COMPLETE
+
RQ1 PRE-TEST CHECKLIST PASS
```

## Gate C — đánh giá cuối RQ2

```text
RQ2 VALIDATION DEVELOPMENT COMPLETE
+
CONFIGURATION LOCK C COMPLETE
+
RQ2 PRE-TEST CHECKLIST PASS
```

Nếu gate nào fail, sửa phần liên quan trước khi chuyển qua gate đó.

---

# 37. Unit Tests tối thiểu

```python
assert train_users.isdisjoint(val_users)
assert train_users.isdisjoint(test_users)
assert val_users.isdisjoint(test_users)
```

First student-skill interaction:

```text
prior_success = 0
prior_failure = 0
```

Sequential evaluation:

```text
predict(t)
xảy ra trước
update(y_t)
```

Problem difficulty OOF:

```text
row/student trong held-out fold
không đóng góp vào fit statistics của chính fold đó
```

---

# 38. Timeline duy nhất

| Tuần | Công việc | Deliverable |
|---|---|---|
| 1 | EDA + viết Methods phần dataset + LLM smoke test | `01_eda.ipynb` |
| 2 | Cleaning + split + cross-fitted features + Configuration Lock A | processed dataset + config |
| 3 | Global/Problem baseline + PFA | baseline/PFA results |
| 4 | BKT + sequential evaluator | BKT results |
| 5 | XGBoost + validation tuning | XGBoost results |
| 6 | Khóa cấu hình B + final RQ1 test + calibration analysis + bootstrap | **RQ1 complete** |
| 7 | BKT state + Knowledge Graph + literature table cập nhật | RQ1 write-up |
| 8 | Candidate generator + B+ + RQ2 validation scenarios | B+ locked |
| 9 | Prompt/LLM development trên RQ2 validation + khóa cấu hình C | Agent / RQ2 protocol locked |
| 10 | RQ2 test scenarios + repeated-run analysis | RQ2 results |
| 11 | Human evaluation + Discussion + Limitations | final analysis |
| 12 | Streamlit + báo cáo + slide | final deliverables |

---

# 39. Viết báo cáo song song

Không chờ tuần 12.

Sau mỗi bước:

```text
save table
save plot
save config
write 3–5 lines interpretation
```

Tuần 1–2:
- Dataset
- Target semantics
- EDA
- Leakage policy
- Split protocol

Tuần 3–6:
- Models
- Sequential evaluation
- Metrics
- RQ1 results

Tuần 7–10:
- Knowledge graph
- RQ2 design
- Agent/B+ protocol
- RQ2 results

---

# 40. Final Limitations

Phải nêu:

- ASSIST09 là dataset cũ, context-specific
- `correct` không phải ground-truth mastery
- BKT mastery là latent model estimate
- single-skill filtering thay đổi population phân tích
- student-disjoint tạo cold-start
- prerequisite graph prototype có giới hạn
- không đo learning gain
- không có RCT
- human evaluation nhỏ
- Local LLM phụ thuộc model/quantization/hardware
- RQ2 không chứng minh causal benefit

---

# 41. Checklist cuối trước TEST

## RQ1

- [ ] EDA hoàn thành
- [ ] Cleaning rule khóa
- [ ] Student split khóa
- [ ] Evaluation mask khóa
- [ ] Cross-fit problem difficulty pass
- [ ] PFA form khóa
- [ ] BKT strategy khóa
- [ ] XGBoost features/encoding khóa
- [ ] Primary metric khóa
- [ ] Calibration protocol khóa
- [ ] Bootstrap protocol khóa
- [ ] Không dùng test trong tuning

## RQ2

- [ ] BKT state definition khóa
- [ ] Knowledge graph khóa
- [ ] Candidate generator khóa
- [ ] B+ khóa
- [ ] Validation scenarios đã dùng xong cho development
- [ ] Prompt khóa
- [ ] Local LLM/config khóa
- [ ] Timeout/retry khóa
- [ ] Rubric khóa
- [ ] Test scenarios chưa được xem trong development

---

# 42. Definition of Done

Đề tài MVP hoàn thành khi:

- [ ] RQ1 có bảng kết quả cuối
- [ ] có uncertainty interval
- [ ] có calibration analysis
- [ ] student state được định nghĩa đúng
- [ ] B+ và Agent dùng cùng input conditions
- [ ] RQ2 có validation/test separation
- [ ] repeated runs được phân tích đúng
- [ ] human evaluation nhỏ nếu khả thi
- [ ] negative result được diễn giải thận trọng
- [ ] research gap có literature evidence
- [ ] limitations rõ
- [ ] demo local tối thiểu
- [ ] code/config đủ tái lập

---

# 43. Việc tiếp theo

Không thêm model.

Làm đúng thứ tự:

```text
1. Tải CSV
2. Đặt vào data/raw/
3. Mở 01_eda.ipynb
4. Đọc schema thật
5. EDA
6. Điền và khóa Configuration Lock A
7. Kiểm tra Gate A
8. Fit/tuning RQ1 trên train/validation
9. Khóa B → Gate B → test RQ1
10. Phát triển RQ2 trên validation scenarios
11. Khóa C → Gate C → test RQ2
```

**EDA được phép bắt đầu ngay.  
Fit/tuning RQ1 bắt đầu khi Gate A đạt. Chỉ mở test RQ1/RQ2 sau khi gate tương ứng đạt.**
