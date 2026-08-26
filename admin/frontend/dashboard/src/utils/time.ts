import { dayjs } from 'frappe-ui'

export const relativeTime = (value) => dayjs(value).fromNow()
