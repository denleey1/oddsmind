Component({
  properties: {
    icon: {
      type: String,
      value: "\ud83d\udced"
    },
    title: {
      type: String,
      value: "\u6682\u65E0\u6570\u636E"
    },
    description: {
      type: String,
      value: ""
    },
    actionText: {
      type: String,
      value: ""
    },
    compact: {
      type: Boolean,
      value: false
    }
  },
  methods: {
    onActionTap() {
      this.triggerEvent("actiontap");
    }
  }
});
