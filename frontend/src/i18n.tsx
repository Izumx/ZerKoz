import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export type Lang = 'ru' | 'kz'

const ru = {
  appSubtitle: 'Мониторинг земель · Жамбылская область',
  live: 'Онлайн',
  offline: 'Нет связи',
  demoSignal: 'Демо: сигнал жителя',
  demoSending: 'Отправляю…',
  botLink: 'Бот для жителей',
  statRed: 'Нарушения',
  statYellow: 'На проверке',
  statGreen: 'Без нарушений',
  statOverdue: 'Срок истёк',
  tabParcels: 'Участки',
  tabSignals: 'Сигналы',
  search: 'Кадастровый номер или адрес',
  all: 'Все',
  exportCsv: 'Экспорт CSV',
  empty: 'Ничего не найдено. Сбросьте фильтры.',
  resetFilters: 'Сбросить',
  showOnMap: 'Показать',
  close: 'Закрыть',
  // легенда и карта
  legendGreen: 'Используется, нарушений нет',
  legendYellow: 'Сигнал или первичная проверка',
  legendRed: 'Зафиксировано нарушение',
  legendSignal: 'Сигнал жителя',
  baseScheme: 'Схема',
  baseSatellite: 'Спутник',
  // участок
  cadastralNo: 'Кадастровый номер',
  purpose: 'Целевое назначение',
  area: 'Площадь',
  ha: 'га',
  owner: 'Землепользователь',
  address: 'Адрес',
  openSignals: 'Открытых сигналов',
  lifecycleTitle: 'Устранение нарушения',
  stepDetected: 'Выявлено',
  stepInProgress: 'Устранение',
  stepClosed: 'Закрыто',
  violationType: 'Тип нарушения',
  chooseViolation: 'Выберите тип',
  recordViolation: 'Зафиксировать нарушение',
  startFix: 'Начать устранение',
  markResolved: 'Устранено',
  returnToState: 'Вернуть государству',
  repeatViolation: 'Зафиксировать повторное нарушение',
  underCheckOn: 'Поставить на проверку',
  underCheckOff: 'Снять с проверки',
  underCheckNote: 'Участок на первичной проверке',
  deadline: 'Контрольный срок',
  saveDeadline: 'Сохранить срок',
  needDeadline: 'Чтобы начать устранение, установите контрольный срок',
  daysLeft: 'осталось {n} дн.',
  daysOverdue: 'просрочено на {n} дн.',
  dueToday: 'срок сегодня',
  noViolation: 'Нарушений не зафиксировано. Если есть основания — поставьте участок на проверку или зафиксируйте нарушение.',
  closedNote: 'Нарушение закрыто',
  photos: 'Фотофиксация',
  uploadPhotos: 'Загрузить фото',
  uploading: 'Загрузка…',
  noPhotos: 'Фото пока нет. Загрузите снимки с места осмотра.',
  byInspector: 'Инспектор',
  byCitizen: 'Житель',
  ndviTitle: 'Индекс вегетации (NDVI), 12 мес.',
  ndviNote: 'симуляция · готово к подключению Sentinel-2',
  ndviLow: 'Низкая вегетация весь сезон — возможное неиспользование',
  ndviOk: 'Сезонная динамика в норме',
  citizenSignals: 'Сигналы жителей',
  history: 'История',
  // сигнал
  signal: 'Сигнал',
  received: 'Получен',
  sourceTelegram: 'через Telegram-бот',
  sourceDemo: 'демо-симуляция',
  sourceSeed: 'тестовые данные',
  location: 'Место',
  outsideParcels: 'вне зарегистрированных участков',
  openParcel: 'Открыть участок',
  takeToCheck: 'Взять в проверку',
  confirmViolation: 'Подтвердить нарушение',
  reject: 'Отклонить',
  markSignalResolved: 'Отметить устранённым',
  backToCheck: 'Вернуть в проверку',
  citizenNotified: 'Житель получит уведомление в Telegram',
  noCitizen: 'Сигнал без Telegram-контакта — уведомление не отправляется',
  // уведомления
  newSignal: 'Новый сигнал {code}',
  newSignalBody: 'Житель сообщил о нарушении',
  saved: 'Сохранено',
  photosUploaded: 'Фото загружены',
  statusChanged: 'Статус сигнала {code}: {status}',
  // история
  hCreated: 'Сигнал получен',
  hStatus: 'Статус: {from} → {to}',
  hLifecycle: 'Этап: {from} → {to}',
  hUpdated: 'Изменены данные участка',
  hPhotos: 'Загружено фото: {count}',
  justNow: 'только что',
  minAgo: '{n} мин назад',
  hAgo: '{n} ч назад',
  dAgo: '{n} дн. назад',
  lifecycle: {
    none: 'Нарушений нет',
    detected: 'Выявлено нарушение',
    in_progress: 'В процессе устранения',
    resolved: 'Устранено',
    returned: 'Возвращено государству',
  },
  violation: { unused: 'Неиспользование', seizure: 'Самозахват', dump: 'Свалка' },
  purposeName: {
    izhs: 'ИЖС',
    agri: 'Сельхозназначение',
    commercial: 'Коммерческое',
    industrial: 'Промышленное',
    lph: 'ЛПХ',
  },
  signalStatus: {
    new: 'Новый',
    checking: 'На проверке',
    confirmed: 'Подтверждён',
    rejected: 'Отклонён',
    resolved: 'Устранён',
  },
  color: { green: 'Норма', yellow: 'Проверка', red: 'Нарушение' },
}

type Dict = typeof ru

const kz: Dict = {
  appSubtitle: 'Жер мониторингі · Жамбыл облысы',
  live: 'Онлайн',
  offline: 'Байланыс жоқ',
  demoSignal: 'Демо: тұрғын сигналы',
  demoSending: 'Жіберілуде…',
  botLink: 'Тұрғындарға арналған бот',
  statRed: 'Бұзушылық',
  statYellow: 'Тексерілуде',
  statGreen: 'Қалыпты',
  statOverdue: 'Мерзімі өтті',
  tabParcels: 'Учаскелер',
  tabSignals: 'Сигналдар',
  search: 'Кадастрлық нөмір немесе мекенжай',
  all: 'Барлығы',
  exportCsv: 'CSV экспорты',
  empty: 'Ештеңе табылмады. Сүзгілерді тазалаңыз.',
  resetFilters: 'Тазалау',
  showOnMap: 'Көрсету',
  close: 'Жабу',
  legendGreen: 'Пайдаланылады, бұзушылық жоқ',
  legendYellow: 'Сигнал немесе бастапқы тексеру',
  legendRed: 'Бұзушылық тіркелді',
  legendSignal: 'Тұрғын сигналы',
  baseScheme: 'Сызба',
  baseSatellite: 'Спутник',
  cadastralNo: 'Кадастрлық нөмір',
  purpose: 'Нысаналы мақсаты',
  area: 'Ауданы',
  ha: 'га',
  owner: 'Жер пайдаланушы',
  address: 'Мекенжай',
  openSignals: 'Ашық сигналдар',
  lifecycleTitle: 'Бұзушылықты жою',
  stepDetected: 'Анықталды',
  stepInProgress: 'Жою',
  stepClosed: 'Жабылды',
  violationType: 'Бұзушылық түрі',
  chooseViolation: 'Түрін таңдаңыз',
  recordViolation: 'Бұзушылықты тіркеу',
  startFix: 'Жоюды бастау',
  markResolved: 'Жойылды',
  returnToState: 'Мемлекетке қайтару',
  repeatViolation: 'Қайталанған бұзушылықты тіркеу',
  underCheckOn: 'Тексеруге қою',
  underCheckOff: 'Тексеруден алу',
  underCheckNote: 'Учаске бастапқы тексеруде',
  deadline: 'Бақылау мерзімі',
  saveDeadline: 'Мерзімді сақтау',
  needDeadline: 'Жоюды бастау үшін бақылау мерзімін белгілеңіз',
  daysLeft: '{n} күн қалды',
  daysOverdue: '{n} күнге кешікті',
  dueToday: 'мерзімі бүгін',
  noViolation: 'Бұзушылық тіркелмеген. Негіз болса — учаскені тексеруге қойыңыз немесе бұзушылықты тіркеңіз.',
  closedNote: 'Бұзушылық жабылды',
  photos: 'Фотобекіту',
  uploadPhotos: 'Фото жүктеу',
  uploading: 'Жүктелуде…',
  noPhotos: 'Әзірге фото жоқ. Тексеру орнынан суреттерді жүктеңіз.',
  byInspector: 'Инспектор',
  byCitizen: 'Тұрғын',
  ndviTitle: 'Вегетация индексі (NDVI), 12 ай',
  ndviNote: 'симуляция · Sentinel-2 қосуға дайын',
  ndviLow: 'Маусым бойы төмен вегетация — пайдаланбау мүмкін',
  ndviOk: 'Маусымдық динамика қалыпты',
  citizenSignals: 'Тұрғындардың сигналдары',
  history: 'Тарих',
  signal: 'Сигнал',
  received: 'Алынды',
  sourceTelegram: 'Telegram-бот арқылы',
  sourceDemo: 'демо-симуляция',
  sourceSeed: 'тестілік деректер',
  location: 'Орны',
  outsideParcels: 'тіркелген учаскелерден тыс',
  openParcel: 'Учаскені ашу',
  takeToCheck: 'Тексеруге алу',
  confirmViolation: 'Бұзушылықты растау',
  reject: 'Қабылдамау',
  markSignalResolved: 'Жойылды деп белгілеу',
  backToCheck: 'Қайта тексеруге алу',
  citizenNotified: 'Тұрғынға Telegram-да хабарлама келеді',
  noCitizen: 'Сигналда Telegram байланысы жоқ — хабарлама жіберілмейді',
  newSignal: 'Жаңа сигнал {code}',
  newSignalBody: 'Тұрғын бұзушылық туралы хабарлады',
  saved: 'Сақталды',
  photosUploaded: 'Фото жүктелді',
  statusChanged: '{code} сигналының мәртебесі: {status}',
  hCreated: 'Сигнал алынды',
  hStatus: 'Мәртебе: {from} → {to}',
  hLifecycle: 'Кезең: {from} → {to}',
  hUpdated: 'Учаске деректері өзгертілді',
  hPhotos: 'Фото жүктелді: {count}',
  justNow: 'жаңа ғана',
  minAgo: '{n} мин бұрын',
  hAgo: '{n} сағ бұрын',
  dAgo: '{n} күн бұрын',
  lifecycle: {
    none: 'Бұзушылық жоқ',
    detected: 'Бұзушылық анықталды',
    in_progress: 'Жою процесінде',
    resolved: 'Жойылды',
    returned: 'Мемлекетке қайтарылды',
  },
  violation: { unused: 'Пайдаланбау', seizure: 'Өз бетінше басып алу', dump: 'Қоқыс үйіндісі' },
  purposeName: {
    izhs: 'ЖТҚ',
    agri: 'Ауыл шаруашылығы',
    commercial: 'Коммерциялық',
    industrial: 'Өнеркәсіптік',
    lph: 'ЖҚШ',
  },
  signalStatus: {
    new: 'Жаңа',
    checking: 'Тексерілуде',
    confirmed: 'Расталды',
    rejected: 'Қабылданбады',
    resolved: 'Жойылды',
  },
  color: { green: 'Қалыпты', yellow: 'Тексеру', red: 'Бұзушылық' },
}

const DICTS: Record<Lang, Dict> = { ru, kz }
type StringKey = { [K in keyof Dict]: Dict[K] extends string ? K : never }[keyof Dict]

interface I18n {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: StringKey, vars?: Record<string, string | number>) => string
  d: Dict
}

const I18nContext = createContext<I18n | null>(null)

function readLang(): Lang {
  try {
    return localStorage.getItem('zherkoz.lang') === 'kz' ? 'kz' : 'ru'
  } catch {
    return 'ru'
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readLang)
  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    document.documentElement.lang = next === 'kz' ? 'kk' : 'ru'
    try {
      localStorage.setItem('zherkoz.lang', next)
    } catch {
      /* приватный режим */
    }
  }, [])
  const value = useMemo<I18n>(() => {
    const d = DICTS[lang]
    const t: I18n['t'] = (key, vars) =>
      (d[key] as string).replace(/\{(\w+)\}/g, (_, name) => String(vars?.[name] ?? `{${name}}`))
    return { lang, setLang, t, d }
  }, [lang, setLang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('I18nProvider отсутствует')
  return ctx
}
