const contactUrl = "https://hc.e-bcc.jp/contact/";

const answers = [
  {
    keys: ["サービス", "内容", "何", "概要"],
    text: "介護DX生産性向上サポートは、施設運営者・責任者向けの伴走型介護DXサービスです。機器選び、補助金申請、現場定着、継続フォローまでワンストップで支援します。"
  },
  {
    keys: ["流れ", "導入", "ステップ", "期間"],
    text: "導入は、無料相談、施設診断・ヒアリング、最適プラン・補助金スキーム提示、導入・現場常駐サポート、定着伴走・継続フォローの5ステップです。導入は内容により1〜3ヶ月が目安です。"
  },
  {
    keys: ["補助金", "助成", "加算", "制度"],
    text: "生産性向上推進体制加算、ICT導入補助金、地域医療介護総合確保基金などの活用余地を確認します。ただし、取得可否は施設の規模や地域、体制によって異なるため断定はできません。無料相談で確認できます。"
  },
  {
    keys: ["費用", "料金", "見積", "いくら"],
    text: "費用は、選定する機器・サービス、施設規模、補助金活用の有無によって大きく変わります。診断・プラン提示の段階で、複数パターンの概算費用とROI試算をご案内します。"
  },
  {
    keys: ["相談", "資料", "申し込み", "問い合わせ", "商談"],
    text: `無料相談、資料請求、商談予約はいずれも問い合わせフォームから受け付けています。\n${contactUrl}`
  },
  {
    keys: ["個人情報", "セキュリティ", "安全"],
    text: "介護記録、健康情報、入居者個人情報などは、個人情報保護法および関連ガイドラインに準拠して取り扱う方針です。製品選定と職員アクセス権限の設計までサポートします。"
  }
];

const fallback = "施設の状況によって案内が変わる内容です。30分の無料相談で、施設規模や現在の課題を伺いながら確認できます。";

const launcher = document.getElementById("chatLauncher");
const widget = document.getElementById("chatWidget");
const closeChat = document.getElementById("closeChat");
const chatBody = document.getElementById("chatBody");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");

function openWidget() {
  widget.classList.add("open");
  launcher.style.display = "none";
  chatInput.focus();
}

function closeWidget() {
  widget.classList.remove("open");
  launcher.style.display = "flex";
}

function appendMessage(text, type) {
  const message = document.createElement("div");
  message.className = `message ${type}`;
  message.textContent = text;
  chatBody.appendChild(message);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function findAnswer(question) {
  const normalized = question.toLowerCase();
  return answers.find((item) => item.keys.some((key) => normalized.includes(key.toLowerCase())));
}

function reply(question) {
  appendMessage(question, "user");
  const typing = document.createElement("div");
  typing.className = "message bot";
  typing.textContent = "確認しています...";
  chatBody.appendChild(typing);
  chatBody.scrollTop = chatBody.scrollHeight;

  window.setTimeout(() => {
    const matched = findAnswer(question);
    typing.textContent = matched ? matched.text : fallback;
  }, 420);
}

launcher.addEventListener("click", openWidget);
closeChat.addEventListener("click", closeWidget);

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => reply(button.dataset.question));
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;
  chatInput.value = "";
  reply(question);
});
