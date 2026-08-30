document.querySelectorAll("[data-birth-fields]").forEach((group) => {
  const year = group.querySelector("[data-birth-year]");
  const month = group.querySelector("[data-birth-month]");
  const day = group.querySelector("[data-birth-day]");
  const form = group.closest("form");

  if (!year || !month || !day || !form) return;

  function daysInMonth() {
    const parsedYear = Number.parseInt(year.value, 10);
    const parsedMonth = Number.parseInt(month.value, 10);
    if (!Number.isInteger(parsedYear) || !Number.isInteger(parsedMonth)) return 31;
    return new Date(parsedYear, parsedMonth, 0).getDate();
  }

  function updateDayOptions() {
    const maxDay = daysInMonth();
    Array.from(day.options).forEach((option) => {
      if (!option.value) return;
      option.disabled = Number.parseInt(option.value, 10) > maxDay;
    });
    if (day.value && Number.parseInt(day.value, 10) > maxDay) {
      day.value = "";
    }
  }

  function sync() {
    const hasYear = year.value.trim() !== "";
    if (!hasYear) {
      month.value = "";
      day.value = "";
    }
    month.disabled = !hasYear;

    const hasMonth = hasYear && month.value !== "";
    if (!hasMonth) {
      day.value = "";
    }
    day.disabled = !hasMonth;
    updateDayOptions();
  }

  year.addEventListener("input", sync);
  month.addEventListener("change", sync);

  form.addEventListener("submit", () => {
    const cleanYear = year.value.trim();
    if (!cleanYear) {
      year.value = "";
      return;
    }

    let birth = cleanYear;
    if (month.value) birth += `-${month.value}`;
    if (month.value && day.value) birth += `-${day.value}`;
    year.value = birth;
  });

  sync();
});
