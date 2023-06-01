// Tab Behaviour
const showTab = (className, tabId) => {
    const tabs = document.getElementsByClassName(className);
    const tab_labels = document.getElementsByClassName(`${className}_label`);
    for (let t = 0; t < tabs.length; t++) {
        tabs[t].style.display = "none";
        tab_labels[t].classList.remove("tab-button-active");
    }
    document.getElementById(tabId).style.display = "block";
    document.getElementById(`${tabId}_label`).classList.add("tab-button-active");
}

// Collapsible Section Behaviour
const showHideCollapsible = (idPrefix) => {
    const add = document.getElementById(`${idPrefix}-add-icon`);
    const remove = document.getElementById(`${idPrefix}-remove-icon`);
    const content = document.getElementById(`${idPrefix}-content`);
    if (content.style.display != 'none') {
        content.style.display = 'none';
        remove.style.display = 'none';
        add.style.display = 'block';
    } else {
        content.style.display = 'block';
        remove.style.display = 'block';
        add.style.display = 'none';
    }
}

// Uncheck checkboxes in group (based on class)
const unCheckOthers = (class_name, name) => {
    const group = document.getElementsByClassName(class_name);
    for (let e of group) {
        if (e.getAttribute('name') != name) {
            e.checked = false;
        }
    }
}
