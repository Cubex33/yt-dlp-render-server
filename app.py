const BOT_TOKEN = "8756312112:AAFmynwxYLwp0qoyiRkEVSvrzRVy6gOemFk";

// Список бесплатных API (никаких ключей!)
const API_LIST = [
  {
    name: "AllMedia",
    url: "https://api.allmedia.app/api/download",
    handler: async (url, quality) => {
      const resp = await fetch("https://api.allmedia.app/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      const json = await resp.json();
      return json.url || json.medias?.[0]?.url || json.video || null;
    }
  },
  {
    name: "Cobalt",
    url: "https://co.wuk.sh/api/json",
    handler: async (url, quality) => {
      const resp = await fetch("https://co.wuk.sh/api/json", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "User-Agent": "Mozilla/5.0"
        },
        body: JSON.stringify({
          url,
          downloadMode: "auto",
          videoQuality: quality === "max" ? "1080" : quality,
          aFormat: "mp4",
          isNoWatermark: true
        })
      });
      const json = await resp.json();
      if (json.status === "success" && json.url) return json.url;
      if (json.url) return json.url;
      if (json.picker?.[0]?.url) return json.picker[0].url;
      return null;
    }
  },
  {
    name: "SnapInsta",
    handler: async (url, quality) => {
      // Только для Instagram
      if (!url.includes("instagram.com")) return null;
      const snapUrl = `https://snapinsta.app/action.php?url=${encodeURIComponent(url)}`;
      const resp = await fetch(snapUrl, {
        headers: { "User-Agent": "Mozilla/5.0" }
      });
      const html = await resp.text();
      const match = html.match(/href="(https:\/\/[^"]*\.(?:mp4|mov)[^"]*)"/i) ||
                    html.match(/data-video="([^"]+)"/);
      return match?.[1] || null;
    }
  }
];

export default {
  async fetch(request) {
    if (request.method !== "POST") return new Response("OK");

    try {
      const data = await request.json();

      // Обработка нажатия на кнопку качества
      if (data.callback_query) {
        await handleCallbackQuery(data.callback_query);
        return new Response("ok");
      }

      if (!data.message) return new Response("ok");
      const chatId = data.message.chat.id;
      let text = data.message.text || "";

      // Извлекаем ссылку из entities
      if (data.message.entities) {
        for (const ent of data.message.entities) {
          if (ent.type === "url") {
            text = text.substring(ent.offset, ent.offset + ent.length);
            break;
          }
        }
      }
      text = text.trim();

      if (!text) return new Response("ok");

      if (text === "/start") {
        await sendMessage(chatId, "🎬 Привет! Отправь ссылку на Reels, TikTok или Shorts — выбери качество и я скачаю через несколько бесплатных сервисов.");
        return new Response("ok");
      }

      if (!text.startsWith("http")) {
        await sendMessage(chatId, "❌ Это не ссылка.");
        return new Response("ok");
      }

      // Предлагаем выбрать качество
      await sendQualityKeyboard(chatId, text);

    } catch (e) {
      console.error(e);
    }
    return new Response("ok");
  }
};

async function handleCallbackQuery(callbackQuery) {
  const chatId = callbackQuery.message.chat.id;
  const messageId = callbackQuery.message.message_id;
  const data = callbackQuery.data; // формат: "quality|max|https://..."

  const parts = data.split('|');
  if (parts.length < 3) return;

  const quality = parts[1];
  const url = parts.slice(2).join('|');

  await answerCallbackQuery(callbackQuery.id);
  await editMessageText(chatId, messageId, `⏳ Качество: ${quality}. Пробую скачать через бесплатные API...`);

  // По очереди пробуем все API
  let videoUrl = null;
  let usedApi = "";

  for (const api of API_LIST) {
    try {
      videoUrl = await api.handler(url, quality);
      if (videoUrl) {
        usedApi = api.name;
        break;
      }
    } catch (e) {
      console.log(`API ${api.name} упал:`, e.message);
    }
  }

  if (videoUrl) {
    await sendMessage(chatId, `✅ Скачано через ${usedApi}! Отправляю видео...`);
    const result = await sendVideo(chatId, videoUrl);
    if (!result.ok) {
      const docRes = await sendDocument(chatId, videoUrl);
      if (!docRes.ok) {
        await sendMessage(chatId, `❌ Не удалось отправить файл.\n🔗 Прямая ссылка:\n${videoUrl}`);
      }
    }
  } else {
    await sendMessage(chatId, "❌ Ни один бесплатный сервис не смог скачать. Возможно, видео удалено или аккаунт приватный.");
  }
}

// --- Клавиатура выбора качества ---
async function sendQualityKeyboard(chatId, url) {
  const keyboard = {
    inline_keyboard: [
      [
        { text: "🔥 Максимальное", callback_data: `quality|max|${url}` },
        { text: "📺 720p", callback_data: `quality|720|${url}` }
      ],
      [
        { text: "📱 480p", callback_data: `quality|480|${url}` }
      ]
    ]
  };
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text: "🎚 Выбери качество видео:",
      reply_markup: keyboard
    })
  });
}

// --- Telegram API helpers ---
async function sendMessage(chatId, text) {
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text })
  });
}

async function editMessageText(chatId, messageId, text) {
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/editMessageText`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, message_id: messageId, text })
  });
}

async function answerCallbackQuery(callbackQueryId) {
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/answerCallbackQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ callback_query_id: callbackQueryId })
  });
}

async function sendVideo(chatId, videoUrl) {
  const res = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendVideo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      video: videoUrl,
      supports_streaming: true
    })
  });
  return await res.json();
}

async function sendDocument(chatId, docUrl) {
  const res = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendDocument`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, document: docUrl })
  });
  return await res.json();
}
