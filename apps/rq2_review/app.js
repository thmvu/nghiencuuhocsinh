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
  '6.EE.B.7':'Giải phương trình đơn giản: cộng hoặc nhân',
  '7.EE.B.4a':'Giải phương trình có nhiều bước hoặc có ngoặc',
  '8.EE.C.7b':'Giải phương trình: bỏ ngoặc, gộp các phần giống nhau'
};
const dimensions = [
  ['AI có dùng đúng thông tin không?', 'Đối chiếu mã bài, kỹ năng và con số trong lời giải thích với bảng. 0: sai rõ hoặc thiếu thông tin quan trọng; 1: đúng một phần, còn mơ hồ; 2: khớp thông tin được cung cấp.'],
  ['AI có giải thích vì sao chọn bài này không?', '0: nói lạc đề hoặc không có lý do; 1: có lý do nhưng chung chung; 2: liên hệ rõ bài được chọn với tình trạng học sinh và những thông tin trong phiếu.'],
  ['AI có nói quá chắc chắn không?', 'Điểm cao nghĩa là biết thận trọng. 0: khẳng định chắc chắn học sinh yếu hoặc chắc chắn tiến bộ khi chưa có căn cứ; 1: có thận trọng nhưng còn khẳng định quá mức; 2: nêu đúng giới hạn của thông tin và cách ước tính.'],
  ['Bạn có hiểu lời giải thích không?', '0: không hiểu được; 1: hiểu một phần hoặc phải đoán; 2: đọc là hiểu AI đã cân nhắc điều gì. Với ba câu hỏi trên, nếu không đọc được ngôn ngữ thì chọn “Không đánh giá được”.']
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
  $('progress-label').textContent = rating ? `${state.rated}/${state.total} tình huống đã nhận xét lời giải thích` : `${state.chosen}/${state.total} tình huống đã chọn bài hoặc ghi chưa đủ thông tin`;
  $('phase-label').textContent = rating ? 'Bước 2 · Chấm lời giải thích' : 'Bước 1 · Lựa chọn của bạn';
  $('previous').disabled = index === 0;
  $('next').disabled = index === state.total - 1;
}
function evidence(shared) {
  const mapping = shared.graph.skill_to_standard;
  const edges = shared.graph.edges;
  return `<details><summary>Xem thêm các kỹ năng và gợi ý thứ tự học</summary>
    <p class="rating-note">Các mũi tên bên dưới là đề xuất thứ tự học của người làm nghiên cứu, chưa có giáo viên toán xác nhận. Hai kỹ năng có cùng tên vẫn có thể được theo dõi riêng.</p>
    <div class="table-scroll"><table><thead><tr><th>Mã kỹ năng</th><th>Kỹ năng</th><th>Mức nắm vững ước tính</th></tr></thead><tbody>${Object.entries(shared.state.skills).map(([id,value]) => `<tr><td>${escape(id)}</td><td>${escape(standards[mapping[id]] || mapping[id])}<span class="skill-code">Mã chương trình: ${escape(mapping[id])}</span></td><td class="number">${percent(value)}</td></tr>`).join('')}</tbody></table></div>
    ${edges.length ? `<ul class="edge-list">${edges.map(edge => `<li>${escape(standards[mapping[edge.prerequisite]] || mapping[edge.prerequisite])} (mã ${escape(edge.prerequisite)}) → ${escape(standards[mapping[edge.target]] || mapping[edge.target])} (mã ${escape(edge.target)})</li>`).join('')}</ul>` : '<p>Tình huống này không cung cấp gợi ý thứ tự học.</p>'}
    </details>`;
}
function renderCase() {
  refreshChrome();
  $('title').textContent = `Tình huống ${index + 1} / ${state.total}`;
  const rating = state.phase === 'rating';
  const shared = current.shared;
  const selection = current.selection;
  const choice = selection?.choice;
  $('content').innerHTML = `<p class="instruction">${rating ? 'Đọc nguyên văn lý do, đối chiếu số liệu rồi chấm từng tiêu chí. Nếu không đọc hiểu được, chọn “Không đánh giá được” ở tiêu chí tương ứng.' : 'Chọn bài bạn thấy hợp lý dựa trên dữ liệu dưới đây, rồi ghi lý do. Bạn sẽ xem AI chọn gì sau khi hoàn tất cả 40 tình huống.'}</p>
    <section class="sheet"><h2>${shared.candidates.length} bài để bạn cân nhắc</h2><p class="sub">Tên kỹ năng giúp bạn hình dung bài thuộc dạng toán nào. Chưa kiểm tra nội dung từng bài; phiếu không có đề bài hay đáp án.</p><div class="context-line"><span>Thông tin được ước tính từ: <b>${shared.state.history_length} lượt làm bài trước đó</b></span><span>Phiếu chưa cho biết học sinh đã luyện mỗi kỹ năng bao nhiêu lần.</span></div>
    <div class="table-scroll"><table class="candidate-table"><thead><tr><th>${rating ? 'Bài' : 'Chọn bài'}</th><th>Kỹ năng</th><th>Mức nắm vững<br>ước tính</th><th>Tỷ lệ làm đúng<br>của nhóm tham khảo</th><th>Số lượt làm bài<br>tham khảo</th></tr></thead><tbody>${shared.candidates.map(c => `<tr><td>${rating ? `<b>${escape(c.problem_id)}</b>` : `<label><input type="radio" name="choice" value="${escape(c.problem_id)}" ${choice === c.problem_id ? 'checked' : ''}>${escape(c.problem_id)}</label>`}</td><td>${escape(standards[shared.graph.skill_to_standard[c.skill_id]] || c.skill_id)}<span class="skill-code">${escape(shared.graph.skill_to_standard[c.skill_id])} · mã kỹ năng ${escape(c.skill_id)}</span></td><td class="number" data-label="Mức nắm vững ước tính">${percent(shared.state.skills[c.skill_id])}</td><td class="number" data-label="Nhóm tham khảo làm đúng">${percent(c.difficulty)}</td><td class="number" data-label="Số lượt tham khảo">${c.support.toLocaleString('vi-VN')}</td></tr>`).join('')}</tbody></table></div>
    <div class="score-help"><b>Cách cân nhắc:</b> xem kỹ năng học sinh còn cần luyện, rồi xem bài có vừa sức không. Mức nắm vững 30% là một ước tính còn thấp; tỷ lệ làm đúng 80% mô tả nhóm tham khảo. Hai số này nói về hai điều khác nhau. Không có quy tắc bắt buộc chọn số thấp nhất hoặc bài dễ nhất.</div>${evidence(shared)}
    ${rating ? `<p class="rating-note">Bạn đã chọn: <b>${selection?.status === 'chosen' ? escape(choice) : 'Không đánh giá được'}</b>. ${escape(selection?.note)}</p>` : `<label class="skip"><input type="radio" name="choice" value="__cannot" ${selection?.status === 'cannot_assess' ? 'checked' : ''}>Không đủ căn cứ để chọn một bài</label><label for="selection-note">Lý do bạn chọn hoặc chưa chọn được</label><textarea id="selection-note" maxlength="2000" placeholder="Bài này có điểm nào phù hợp? Có thông tin nào khiến bạn chưa chắc?">${escape(selection?.note)}</textarea><div class="actions"><button id="save-selection">Lưu và sang phiếu tiếp</button><small>Bạn có thể sửa trước khi xem AI chọn gì.</small></div>`}</section>
    ${rating ? `<section class="sheet"><h2>Lời giải thích cần chấm</h2><p class="sub">Bài AI đã chọn: <b>${escape(current.choice)}</b>. Đây là lời giải thích gốc. Nếu không hiểu ngôn ngữ, hãy ghi rõ; bạn không cần tự dịch hay đoán.</p><blockquote class="reason">${escape(current.reason)}</blockquote><div class="score-help">0 = sai hoặc thiếu nghiêm trọng · 1 = một phần hoặc còn mơ hồ · 2 = đầy đủ theo dữ liệu.<br>Không đánh giá được ≠ điểm 0. Không đọc được lời giải thích thì chọn “Không đánh giá được” cho độ đúng, lý do chọn và mức thận trọng. Bạn vẫn có thể đánh giá nó có dễ hiểu với mình không.</div>${dimensions.map(([name,help], i) => `<div class="rubric"><div><h3>${name}</h3><p>${help}</p></div><label><span class="sr-name">${name}</span><select id="score-${i}" aria-label="${name}"><option value="">Chọn mức đánh giá</option>${[['0','0 — Sai / thiếu'],['1','1 — Một phần'],['2','2 — Đầy đủ'],['NA','Không đánh giá được']].map(([value,label]) => `<option value="${value}" ${current.rating && (current.rating.scores[i] === null ? value === 'NA' : value === String(current.rating.scores[i])) ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div>`).join('')}<label for="rating-note">Bạn thấy điều gì đúng, chưa đúng hoặc chưa hiểu?</label><textarea id="rating-note" maxlength="2000" placeholder="Ghi số liệu sai, lý do phù hợp hoặc hạn chế đọc hiểu…">${escape(current.rating?.note)}</textarea><div class="actions"><button id="save-rating">Lưu và sang phiếu tiếp</button><small>Đây là nhận xét của bạn; chưa phải đánh giá của giáo viên toán.</small></div></section>` : ''}`;
  $('content').querySelectorAll('input,textarea,select').forEach(element => element.addEventListener('input', () => { dirty = true; }));
  $('save-selection')?.addEventListener('click', saveSelection);
  $('save-rating')?.addEventListener('click', saveRating);
  if (state.phase === 'ready') renderReady();
}
function renderReady() {
  $('content').insertAdjacentHTML('beforeend', `<section class="sheet ready"><h2>Đã hoàn tất lựa chọn riêng của bạn</h2><p>Khi xem AI chọn gì, lựa chọn riêng của bạn ở bước 1 sẽ được giữ lại. Bạn vẫn có thể sửa điểm lời giải thích, mỗi lần sửa đều được lưu.</p><button id="reveal">Bắt đầu chấm lời giải thích</button></section>`);
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
    $('content').innerHTML = `<section class="sheet"><h2>Kết quả bạn đã tự nhận xét</h2><p class="sub">${escape(state.reviewer || 'Chưa nhập người chấm')}. Đây là tự nhận xét của người làm nghiên cứu, chưa phải đánh giá của người có chuyên môn độc lập.</p><table class="summary-table"><tbody><tr><td>Tình huống đã chọn bài hoặc ghi chưa đủ thông tin</td><td>${state.chosen}/${state.total}</td></tr><tr><td>Tình huống đã nhận xét lời giải thích</td><td>${state.rated}/${state.total}</td></tr><tr><td>Tình huống chấm được cả bốn câu hỏi</td><td>${result.fully_scored}/${state.total}</td></tr><tr><td>Điểm trung bình tổng hợp (tối đa 2)</td><td>${result.rubric.unconditional_mean === null ? 'Chưa đánh giá đủ' : result.rubric.unconditional_mean.toFixed(3) + ' / 2'}</td></tr><tr><td>Số lần bạn và AI chọn cùng bài</td><td>${result.agreement_with_agent_descriptive === null ? 'Ẩn cho đến bước 2' : result.agreement_with_agent_descriptive + ' / ' + result.human_choices_assessable}</td></tr></tbody></table><p class="completion">Hai bên chọn giống nhau chưa có nghĩa bài đó chắc chắn tốt cho học sinh. Các điểm này được dùng để ghi nhận nhận xét của bạn.</p><div class="actions"><button id="resume">Quay lại phiếu</button></div></section>`;
    $('resume').addEventListener('click', () => loadCase(false));
  } catch (error) { feedback(error.message,true); }
}
$('previous').addEventListener('click', async () => { if (dirty && !confirm('Bỏ thay đổi chưa lưu?')) return; index = Math.max(0,index-1); await loadCase(false); });
$('next').addEventListener('click', async () => { if (dirty && !confirm('Bỏ thay đổi chưa lưu?')) return; index = Math.min(state.total-1,index+1); await loadCase(false); });
$('summary-button').addEventListener('click', showSummary);
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
(async () => { try { state = await api('/api/state'); token = state.token; const done = state.phase === 'rating' ? state.completed_rating : state.completed_selection; index = Array.from({length:state.total},(_,i)=>i).find(i=>!done.includes(i)) ?? 0; await loadCase(false); } catch (error) { feedback(error.message,true); } })();
