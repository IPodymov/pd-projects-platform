export const fieldLabels: Record<string, string> = {
  non_field_errors: 'Проверка данных',
  text: 'Результат',
  feedback: 'Замечание',
  remarks: 'Замечание',
  previous: 'Предыдущая отправка',
  title: 'Название',
  due_at: 'Срок',
  classroom: 'Класс',
  email: 'Почта',
  users: 'Участники',
  online_url: 'Онлайн-ссылка',
  location: 'Место',
  reviewer: 'Проверяющий',
  institution: 'Учреждение',
  milestone: 'Этап',
  criteria: 'Критерии',
  assignment: 'Задание',
  password: 'Пароль',
  current_password: 'Текущий пароль',
  new_password: 'Новый пароль',
  first_name: 'Имя',
  last_name: 'Фамилия',
  code: 'Код подтверждения',
  file: 'Файл',
  project: 'Проект',
  course: 'Курс',
  start_at: 'Начало',
  end_at: 'Окончание',
  capacity: 'Количество мест',
  description: 'Описание',
  name: 'Название',
}
export function fieldLabel(key: string): string {
  return fieldLabels[key] || 'Поле формы'
}
export function readableMessage(message: string): string {
  const translations: Record<string, string> = {
    'This field is required.': 'Заполните это поле.',
    'This field may not be blank.': 'Поле не должно быть пустым.',
    'This field may not be null.': 'Укажите значение.',
    'Enter a valid email address.': 'Введите адрес почты в формате name@example.com.',
    'A valid integer is required.': 'Введите целое число.',
    'Not a valid string.': 'Введите текст.',
    'Invalid pk "': 'Выбранная запись недоступна.',
  }
  return (
    translations[message] ||
    (/^Invalid pk /.test(message)
      ? 'Выбранная запись больше недоступна. Выберите другую.'
      : message)
  )
}
export function statusMessage(status: number): string {
  if (status === 401) return 'Сессия завершилась или вход не выполнен. Войдите в аккаунт повторно.'
  if (status === 403)
    return 'У вашего аккаунта нет прав на это действие. Обратитесь к преподавателю или администратору.'
  if (status === 404)
    return 'Запись не найдена: она могла быть удалена или недоступна вашему аккаунту. Обновите список.'
  if (status === 409 || status === 428)
    return 'Данные изменились или требуют обновления. Обновите запись и проверьте данные перед сохранением.'
  if (status === 413) return 'Файл слишком большой. Уменьшите его размер и загрузите снова.'
  if (status === 429)
    return 'Слишком много запросов за короткое время. Подождите немного и повторите действие.'
  if (status >= 500)
    return 'На сервере произошёл сбой. Повторите действие через несколько минут. Если ошибка повторяется, обратитесь к администратору.'
  return 'Не удалось выполнить действие. Проверьте введённые данные и повторите попытку.'
}
export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    if (error.name === 'AbortError' || error.name === 'TimeoutError')
      return 'Не удалось дождаться ответа сервера. Проверьте соединение и повторите действие.'
    if (error instanceof TypeError && /fetch|network|load failed/i.test(error.message))
      return 'Не удалось связаться с сервером. Проверьте подключение к интернету и повторите действие. Если интернет работает, сервис может быть временно недоступен.'
    if (/[а-яё]/i.test(error.message)) return 'fields' in error ? String(error) : error.message
  }
  return 'Произошла непредвиденная ошибка. Повторите действие. Если она повторяется, обратитесь к администратору.'
}
export function jobErrorMessage(code: string): string {
  const messages: Record<string, string> = {
    access_revoked: 'Доступ был отозван. Обратитесь к владельцу проекта или администратору.',
    extraction_failed:
      'Не удалось прочитать текст документа. Проверьте, что файл открывается, и загрузите его повторно.',
    comparison_failed:
      'Не удалось сравнить документы. Повторите сравнение; если ошибка повторяется, обратитесь к администратору.',
    repository_disabled: 'Репозиторий отключён. Подключите его повторно перед синхронизацией.',
    provider_sync_failed:
      'Не удалось получить данные из сервиса репозиториев. Проверьте доступ к репозиторию и повторите синхронизацию позже.',
  }
  return (
    messages[code] ||
    'Не удалось завершить обработку. Повторите действие позже; если ошибка повторяется, обратитесь к администратору.'
  )
}
