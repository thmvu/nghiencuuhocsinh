let state, current, index = 0, token, dirty = false;
const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const percent = value => (100 * value).toLocaleString('vi-VN', {maximumFractionDigits: 1}) + '%';
// Short Vietnamese paraphrases of CCSS, for reviewer orientation only.
const standards = {
  '6.NS.A.1':'Chia phân số và bài toán liên quan',
  '6.RP.A.3a':'Bảng tỉ số tương đương', '6.RP.A.3b':'Tỉ suất đơn vị: đơn giá, tốc độ',
  '6.RP.A.3c':'Phần trăm của một đại lượng', '6.RP.A.3d':'Đổi đơn vị đo bằng tỉ số',
  '7.RP.A.1':'Tỉ suất đơn vị với đại lượng phân số', '7.RP.A.2a':'Nhận diện quan hệ tỉ lệ',
  '7.RP.A.2b':'Xác định hằng số tỉ lệ', '7.RP.A.2c':'Viết phương trình quan hệ tỉ lệ',
  '7.RP.A.3':'Bài toán tỉ số, phần trăm nhiều bước',
  '6.EE.B.5':'Kiểm tra nghiệm bằng thay giá trị', '6.EE.B.6':'Dùng biến biểu diễn đại lượng',
  '6.EE.B.7':'Phương trình x + p = q hoặc px = q',
  '7.EE.B.4a':'Phương trình px + q = r hoặc p(x + q) = r',
  '8.EE.C.7b':'Phương trình tuyến tính: khai triển, thu gọn'
};
const dimensions = [
  ['Nhất quán bằng chứng', 'Số liệu, mã bài, kỹ năng và quan hệ có đúng với dữ liệu được cung cấp không?'],
  ['Liên quan lựa chọn', 'Lý do có gắn với bài được chọn và giải thích được sự cân nhắc không?'],
  ['Nhận biết giới hạn', 'Có phân biệt ước lượng với sự thật, tránh khẳng định graph nhân quả hoặc chắc chắn cải thiện học tập không?'],
  ['Dễ hiểu', 'Bạn có đọc hiểu được lý do, đủ rõ và ngắn để hiểu lựa chọn không?']
];

async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST', headers:{'Content-Type':'application/json','X-Review-Token':token}, body:JSON.stringify(body)} : {});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Chưa thực hiện được.');
  return value;
}
function feedback(text, error = false) { $('feedback').textContent = text; $('feedback').classList.toggle('error', error); }
function refreshChrome() {
  $('demo-banner').hidden = !state.demo;
  if (state.reviewer) { $('reviewer').value = state.reviewer; $('reviewer').readOnly = true; }
  const rating = state.phase === 'rating';
  $('step-selection').classList.toggle('active', !rating);
  $('step-rating').classList.toggle('active', rating);
  $('progress').max = state.total;
  $('progress').value = rating ? state.rated : state.chosen;
  $('progress-label').textContent = rating ? `${state.rated}/${state.total} phiếu đã ghi nhận điểm hoặc hạn chế` : `${state.chosen}/${state.total} phiếu đã chọn hoặc ghi không đánh giá được`;
  $('phase-label').textContent = rating ? 'Bước 2 · Chấm lời giải thích' : 'Bước 1 · Lựa chọn của bạn';
  $('previous').disabled = index === 0;
  $('next').disabled = index === state.total - 1;
}
function evidence(shared) {
  const mapping = shared.graph.skill_to_standard;
  const edges = shared.graph.edges;
  return `<details><summary>Xem mastery toàn bộ kỹ năng và các liên kết</summary>
    <p class="rating-note">Liên kết là giả định chương trình của tác giả, chưa được chuyên gia xác nhận. Mỗi skill ID giữ một state riêng dù cùng mã chuẩn.</p>
    <div class="table-scroll"><table><thead><tr><th>Skill ID</th><th>Mã chuẩn / diễn giải ngắn</th><th>Mastery BKT</th></tr></thead><tbody>${Object.entries(shared.state.skills).map(([id,value]) => `<tr><td>${escape(id)}</td><td>${escape(mapping[id])}<span class="skill-code">${escape(standards[mapping[id]] || '')}</span></td><td class="number">${percent(value)}</td></tr>`).join('')}</tbody></table></div>
    ${edges.length ? `<ul class="edge-list">${edges.map(edge => `<li>${escape(mapping[edge.prerequisite])} (ID ${escape(edge.prerequisite)}) → ${escape(mapping[edge.target])} (ID ${escape(edge.target)})</li>`).join('')}</ul>` : '<p>Đầu vào này không có cạnh graph.</p>'}
    <details><summary>Số liệu gốc với đầy đủ độ chính xác</summary><pre class="raw">${escape(JSON.stringify(shared,null,2))}</pre></details></details>`;
}
function renderCase() {
  refreshChrome();
  $('title').textContent = `${current.code} / ${state.total}`;
  const rating = state.phase === 'rating';
  const shared = current.shared;
  const selection = current.selection;
  const choice = selection?.choice;
  $('content').innerHTML = `<p class="instruction">${rating ? 'Đọc nguyên văn lý do, đối chiếu số liệu rồi chấm từng tiêu chí. Nếu không đọc hiểu được, chọn “Không đánh giá được” ở tiêu chí tương ứng.' : 'Chọn bài bạn thấy hợp lý dựa trên dữ liệu dưới đây, rồi ghi lý do. Lựa chọn của Agent sẽ được ẩn cho tới khi bạn hoàn tất toàn bộ phiếu.'}</p>
    <section class="sheet"><h2>${shared.candidates.length} bài ứng viên</h2><p class="sub">Giữ thứ tự input gốc. Nhãn tiếng Việt diễn giải mã chuẩn CCSS, chưa xác minh nội dung từng bài. Không có đề bài hoặc đáp án.</p><div class="context-line"><span>Lịch sử đã dùng: <b>${shared.state.history_length} tương tác</b></span><span>Mastery chưa kèm số lượt quan sát theo từng kỹ năng trong phiếu này.</span></div>
    <div class="table-scroll"><table><thead><tr><th>${rating ? 'Bài' : 'Chọn bài'}</th><th>Kỹ năng</th><th>Mastery BKT</th><th>Tỷ lệ đúng TRAIN</th><th>Support</th></tr></thead><tbody>${shared.candidates.map(c => `<tr><td>${rating ? `<b>${escape(c.problem_id)}</b>` : `<label><input type="radio" name="choice" value="${escape(c.problem_id)}" ${choice === c.problem_id ? 'checked' : ''}>${escape(c.problem_id)}</label>`}</td><td>${escape(standards[shared.graph.skill_to_standard[c.skill_id]] || c.skill_id)}<span class="skill-code">${escape(shared.graph.skill_to_standard[c.skill_id])} · skill ID ${escape(c.skill_id)}</span></td><td class="number">${percent(shared.state.skills[c.skill_id])}</td><td class="number">${percent(c.difficulty)}</td><td class="number">${c.support.toLocaleString('vi-VN')}</td></tr>`).join('')}</tbody></table></div>
    ${evidence(shared)}
    ${rating ? `<p class="rating-note">Bạn đã chọn: <b>${selection?.status === 'chosen' ? escape(choice) : 'Không đánh giá được'}</b>. ${escape(selection?.note)}</p>` : `<label class="skip"><input type="radio" name="choice" value="__cannot" ${selection?.status === 'cannot_assess' ? 'checked' : ''}>Không đủ căn cứ để chọn một bài</label><label for="selection-note">Lý do bạn chọn hoặc chưa chọn được</label><textarea id="selection-note" maxlength="2000" placeholder="Ví dụ: ưu tiên kỹ năng mastery thấp, nhưng số liệu còn chưa đủ…">${escape(selection?.note)}</textarea><div class="actions"><button id="save-selection">Lưu và sang phiếu tiếp</button><small>Có thể sửa trước khi mở phần Agent.</small></div>`}</section>
    ${rating ? `<section class="sheet"><h2>Lời giải thích cần chấm</h2><p class="sub">Bài được Agent chọn: <b>${escape(current.choice)}</b>. Giữ nguyên văn bản gốc, không dịch hoặc sửa trước khi chấm.</p><blockquote class="reason">${escape(current.reason)}</blockquote><div class="score-help">0 = sai hoặc thiếu nghiêm trọng · 1 = một phần hoặc còn mơ hồ · 2 = đầy đủ theo dữ liệu.<br>Không đánh giá được ≠ điểm 0. Không hiểu ngôn ngữ thì ghi hạn chế; đừng đoán mức đúng/sai bằng chứng.</div>${dimensions.map(([name,help], i) => `<div class="rubric"><div><h3>${name}</h3><p>${help}</p></div><label><span class="sr-name">${name}</span><select id="score-${i}" aria-label="${name}"><option value="">Chọn mức đánh giá</option>${[['0','0 — Sai / thiếu'],['1','1 — Một phần'],['2','2 — Đầy đủ'],['NA','Không đánh giá được']].map(([value,label]) => `<option value="${value}" ${current.rating && (current.rating.scores[i] === null ? value === 'NA' : value === String(current.rating.scores[i])) ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div>`).join('')}<label for="rating-note">Nhận xét và căn cứ chấm</label><textarea id="rating-note" maxlength="2000" placeholder="Ghi số liệu sai, lý do phù hợp hoặc hạn chế đọc hiểu…">${escape(current.rating?.note)}</textarea><div class="actions"><button id="save-rating">Lưu và sang phiếu tiếp</button><small>Điểm tự đánh giá, không thay expert review.</small></div></section>` : ''}`;
  $('content').querySelectorAll('input,textarea,select').forEach(element => element.addEventListener('input', () => { dirty = true; }));
  $('save-selection')?.addEventListener('click', saveSelection);
  $('save-rating')?.addEventListener('click', saveRating);
  if (state.phase === 'ready') renderReady();
}
function renderReady() {
  $('content').insertAdjacentHTML('beforeend', `<section class="sheet ready"><h2>Đã hoàn tất lựa chọn riêng của bạn</h2><p>Khi mở phần Agent, các lựa chọn ở bước 1 sẽ được khóa để tránh sửa theo kết quả nhìn thấy. Điểm lời giải thích vẫn có thể chỉnh và có lịch sử lưu.</p><button id="reveal">Bắt đầu chấm lời giải thích</button></section>`);
  $('reveal').addEventListener('click', async () => { try { await save({action:'reveal'}); index = 0; await loadCase(false); } catch (error) { feedback(error.message,true); } });
}
async function loadCase(checkDirty = true) {
  if (checkDirty && dirty && !confirm('Phiếu đang có thay đổi chưa lưu. Bỏ thay đổi để chuyển phiếu?')) return;
  current = await api(`/api/case?index=${index}`);
  dirty = false;
  renderCase();
}
async function save(body) {
  const result = await api('/api/save', {...body,version:state.version,reviewer:$('reviewer').value});
  state = result;
  dirty = false;
  feedback('Đã lưu trên máy.');
}
async function saveSelection() {
  try {
    const choice = document.querySelector('input[name="choice"]:checked')?.value;
    if (!choice) throw new Error('Chọn một bài hoặc ghi không đủ căn cứ.');
    await save({action:'selection',index,choice:choice === '__cannot' ? null : choice,status:choice === '__cannot' ? 'cannot_assess' : 'chosen',note:$('selection-note').value});
    if (state.phase !== 'ready') index = Array.from({length:state.total},(_,i)=>(index+1+i)%state.total).find(i=>!state.completed_selection.includes(i)) ?? index;
    await loadCase(false);
  } catch (error) { feedback(error.message,true); }
}
async function saveRating() {
  try {
    const values = dimensions.map((_,i) => $(`score-${i}`).value);
    if (values.some(value => value === '')) throw new Error('Đánh giá đủ bốn tiêu chí, có thể chọn không đánh giá được.');
    await save({action:'rating',index,scores:values.map(value => value === 'NA' ? null : Number(value)),note:$('rating-note').value});
    if (state.rated === state.total) return showSummary();
    index = Math.min(index+1,state.total-1);
    await loadCase(false);
  } catch (error) { feedback(error.message,true); }
}
async function showSummary() {
  if (dirty && !confirm('Bỏ thay đổi chưa lưu để xem tiến độ?')) return;
  try {
    const result = await api('/api/summary');
    dirty = false; refreshChrome();
    $('title').textContent = 'Tiến độ rà soát';
    $('content').innerHTML = `<section class="sheet"><h2>Tác giả tự đánh giá</h2><p class="sub">${escape(state.reviewer || 'Chưa nhập người chấm')}. Không phải người chấm chuyên gia độc lập.</p><table class="summary-table"><tbody><tr><td>Phiếu đã ghi lựa chọn / hạn chế</td><td>${state.chosen}/${state.total}</td></tr><tr><td>Phiếu đã ghi điểm / hạn chế</td><td>${state.rated}/${state.total}</td></tr><tr><td>Phiếu đủ cả bốn điểm số</td><td>${result.fully_scored}/${state.total}</td></tr><tr><td>Điểm rubric không điều kiện</td><td>${result.rubric.unconditional_mean === null ? 'Chưa đánh giá đủ' : result.rubric.unconditional_mean.toFixed(3) + ' / 2'}</td></tr><tr><td>Lựa chọn của bạn trùng Agent (mô tả)</td><td>${result.agreement_with_agent_descriptive === null ? 'Ẩn cho đến bước 2' : result.agreement_with_agent_descriptive + ' / ' + result.human_choices_assessable}</td></tr></tbody></table><p class="completion">Kết quả tự chấm không biến lựa chọn thành đáp án vàng. Không mở TEST, không khóa Lock C, không xuất dữ liệu huấn luyện.</p><div class="actions"><button id="resume">Quay lại phiếu</button></div></section>`;
    $('resume').addEventListener('click', () => loadCase(false));
  } catch (error) { feedback(error.message,true); }
}
$('previous').addEventListener('click', async () => { if (dirty && !confirm('Bỏ thay đổi chưa lưu?')) return; index = Math.max(0,index-1); await loadCase(false); });
$('next').addEventListener('click', async () => { if (dirty && !confirm('Bỏ thay đổi chưa lưu?')) return; index = Math.min(state.total-1,index+1); await loadCase(false); });
$('summary-button').addEventListener('click', showSummary);
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
(async () => { try { state = await api('/api/state'); token = state.token; const done = state.phase === 'rating' ? state.completed_rating : state.completed_selection; index = Array.from({length:state.total},(_,i)=>i).find(i=>!done.includes(i)) ?? 0; await loadCase(false); } catch (error) { feedback(error.message,true); } })();
