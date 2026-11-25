// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 by-jsk. Independent mobile interface for Stellarium.
#pragma once
#include <QObject>
#include <QJsonObject>
#include <QPointer>
#include <functional>
class QGraphicsWidget;
class QGraphicsProxyWidget;
class QWidget;
class QVBoxLayout;
class QToolButton;
class QLabel;
class MobileShell : public QObject
{
public:
    explicit MobileShell(QGraphicsWidget* parent);
    static void prepare();
    static void fitDialog(QWidget* dialog, QGraphicsProxyWidget* proxy);
    QString trm(const char* key) const;
protected:
    bool eventFilter(QObject* watched, QEvent* event) override;
private:
    void layout();
    void toolbar();
    void page(const char* title);
    void settings();
    void help();
    void about();
    void languages();
    void search();
    void time();
    void location();
    void tools();
    void updates();
    void applyLanguage();
    void smokeTest();
    void action(const QString& id);
    void addButton(const QString& label, const std::function<void()>& callback);
    void addText(const QString& text);
    QGraphicsWidget* root;
    QGraphicsProxyWidget* bar = nullptr;
    QGraphicsProxyWidget* panel = nullptr;
    QWidget* content = nullptr;
    QVBoxLayout* body = nullptr;
    QJsonObject strings;
    QString language;
    QString currentPage;
};
