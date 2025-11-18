// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2023 David Carter <dcarter@david.carter.ca>             *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 **************************************************************************/

#include <QColorDialog>
#include <QDesktopServices>
#include <QIODevice>
#include <QItemSelectionModel>
#include <QSignalBlocker>
#include <QMenu>
#include <QMessageBox>
#include <QString>
#include <QStringList>
#include <QTextStream>
#include <QVariant>
#include <limits>


#include <App/Application.h>
#include <App/License.h>
#include <Base/Interpreter.h>
#include <Base/Quantity.h>
#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/InputField.h>
#include <Gui/PrefWidgets.h>
#include <Gui/SpinBox.h>
#include <Gui/WaitCursor.h>

#include <Mod/Material/App/Exceptions.h>
#include <Mod/Material/App/MaterialLibrary.h>
#include <Mod/Material/App/ModelManager.h>
#include <Mod/Material/App/ModelUuids.h>

#include "MaterialDelegate.h"
#include "MaterialSave.h"
#include "MaterialsEditor.h"
#include "ModelSelect.h"
#include "ui_MaterialsEditor.h"


using namespace MatGui;

/* TRANSLATOR MatGui::MaterialsEditor */

MaterialsEditor::MaterialsEditor(Materials::MaterialFilter filter, QWidget* parent)
    : QDialog(parent)
    , ui(new Ui_MaterialsEditor)
    , _material(std::make_shared<Materials::Material>())
    , _rendered(nullptr)
    , _materialSelected(false)
    , _recentMax(0)
    , _filter(filter)
{
    setup();
}

MaterialsEditor::MaterialsEditor(QWidget* parent)
    : QDialog(parent)
    , ui(new Ui_MaterialsEditor)
    , _material(std::make_shared<Materials::Material>())
    , _rendered(nullptr)
    , _materialSelected(false)
    , _recentMax(0)
{
    setup();
}

void MaterialsEditor::setup()
{
    Gui::WaitCursor wc;
    ui->setupUi(this);

    _warningIcon = QIcon(QStringLiteral(":/icons/Warning.svg"));

    getFavorites();
    getRecents();

    createMaterialTree();
    createPhysicalTree();
    createAppearanceTree();
    createPreviews();
    setMaterialDefaults();

    // Reset to previous size
    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Editor");
    auto width = param->GetInt("EditorWidth", 835);
    auto height = param->GetInt("EditorHeight", 542);

    resize(width, height);

    ui->buttonURL->setIcon(QIcon(QStringLiteral(":/icons/internet-web-browser.svg")));

    connect(ui->standardButtons->button(QDialogButtonBox::Ok), &QPushButton::clicked, this, &MaterialsEditor::accept);
    connect(ui->standardButtons->button(QDialogButtonBox::Cancel),
        &QPushButton::clicked, this, &MaterialsEditor::reject);
    connect(ui->standardButtons->button(QDialogButtonBox::Save),
            &QPushButton::clicked,
            this,
            &MaterialsEditor::onSave);

    connect(ui->editName, &QLineEdit::textEdited, this, &MaterialsEditor::onName);
    connect(ui->editName, &QLineEdit::textEdited, this, &MaterialsEditor::onEditorNameChanged);
    connect(ui->editAuthor, &QLineEdit::textEdited, this, &MaterialsEditor::onAuthor);
    connect(ui->editLicense, &QLineEdit::textEdited, this, &MaterialsEditor::onLicense);
    connect(ui->editSourceURL, &QLineEdit::textEdited, this, &MaterialsEditor::onSourceURL);
    connect(ui->editSourceReference,
            &QLineEdit::textEdited,
            this,
            &MaterialsEditor::onSourceReference);
    connect(ui->editDescription, &QTextEdit::textChanged, this, &MaterialsEditor::onDescription);

    connect(ui->buttonURL, &QPushButton::clicked, this, &MaterialsEditor::onURL);
    connect(ui->buttonPhysicalAdd, &QPushButton::clicked, this, &MaterialsEditor::onPhysicalAdd);
    connect(ui->buttonPhysicalRemove,
            &QPushButton::clicked,
            this,
            &MaterialsEditor::onPhysicalRemove);
    connect(ui->buttonAppearanceAdd,
            &QPushButton::clicked,
            this,
            &MaterialsEditor::onAppearanceAdd);
    connect(ui->buttonAppearanceRemove,
            &QPushButton::clicked,
            this,
            &MaterialsEditor::onAppearanceRemove);
    connect(ui->buttonInheritNew,
            &QPushButton::clicked,
            this,
            &MaterialsEditor::onInheritNewMaterial);
    connect(ui->buttonNew, &QPushButton::clicked, this, &MaterialsEditor::onNewMaterial);
    connect(ui->buttonFavorite, &QPushButton::clicked, this, &MaterialsEditor::onFavourite);

    QItemSelectionModel* selectionModel = ui->treeMaterials->selectionModel();
    connect(selectionModel,
            &QItemSelectionModel::selectionChanged,
            this,
            &MaterialsEditor::onSelectMaterial);
    connect(ui->treeMaterials, &QTreeView::doubleClicked, this, &MaterialsEditor::onDoubleClick);

    // Disabled for now. This will be revisited post 1.0
#if 0
    ui->treeMaterials->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(ui->treeMaterials,
            &QWidget::customContextMenuRequested,
            this,
            &MaterialsEditor::onContextMenu);
#endif

    // Connect all data-changing widgets to the onDataChanged slot.
    connect(ui->editAuthor, &QLineEdit::textEdited, this, &MaterialsEditor::onDataChanged);
    connect(ui->editLicense, &QLineEdit::textEdited, this, &MaterialsEditor::onDataChanged);
    connect(ui->editSourceURL, &QLineEdit::textEdited, this, &MaterialsEditor::onDataChanged);
    connect(ui->editSourceReference, &QLineEdit::textEdited, this, &MaterialsEditor::onDataChanged);
    connect(ui->editDescription, &QTextEdit::textChanged, this, &MaterialsEditor::onDataChanged);

    // Start the editor in a "New, Unsaved" state by default.
    createTransientItem();
}

void MaterialsEditor::getFavorites()
{
    _favorites.clear();

    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Favorites");
    int count = param->GetInt("Favorites", 0);
    for (int i = 0; static_cast<long>(i) < count; i++) {
        QString key = QStringLiteral("FAV%1").arg(i);
        QString uuid = QString::fromStdString(param->GetASCII(key.toStdString().c_str(), ""));
        if (_filter.modelIncluded(uuid)) {
            _favorites.push_back(uuid);
        }
    }
}

void MaterialsEditor::saveFavorites()
{
    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Favorites");

    // Clear out the existing favorites
    int count = param->GetInt("Favorites", 0);
    for (int i = 0; static_cast<long>(i) < count; i++) {
        QString key = QStringLiteral("FAV%1").arg(i);
        param->RemoveASCII(key.toStdString().c_str());
    }

    // Add the current values
    param->SetInt("Favorites", _favorites.size());
    int j = 0;
    for (auto& favorite : _favorites) {
        QString key = QStringLiteral("FAV%1").arg(j);
        param->SetASCII(key.toStdString().c_str(), favorite.toStdString());

        j++;
    }
}

void MaterialsEditor::addFavorite(const QString& uuid)
{
    // Ensure it is a material. New, unsaved materials will not be
    try {
        auto material = Materials::MaterialManager::getManager().getMaterial(uuid);
        Q_UNUSED(material)
    }
    catch (const Materials::MaterialNotFound&) {
        return;
    }

    if (!isFavorite(uuid)) {
        _favorites.push_back(uuid);
        saveFavorites();
        refreshMaterialTree();
    }
}

void MaterialsEditor::removeFavorite(const QString& uuid)
{
    if (isFavorite(uuid)) {
        _favorites.remove(uuid);
        saveFavorites();
        refreshMaterialTree();
    }
}

bool MaterialsEditor::isFavorite(const QString& uuid) const
{
    for (auto& it : _favorites) {
        if (it == uuid) {
            return true;
        }
    }
    return false;
}


void MaterialsEditor::getRecents()
{
    _recents.clear();

    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Recent");
    _recentMax = param->GetInt("RecentMax", 5);
    int count = param->GetInt("Recent", 0);
    for (int i = 0; static_cast<long>(i) < count; i++) {
        QString key = QStringLiteral("MRU%1").arg(i);
        QString uuid = QString::fromStdString(param->GetASCII(key.toStdString().c_str(), ""));
        if (_filter.modelIncluded(uuid)) {
            _recents.push_back(uuid);
        }
    }
}

void MaterialsEditor::saveRecents()
{
    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Recent");

    // Clear out the existing favorites
    int count = param->GetInt("Recent", 0);
    for (int i = 0; static_cast<long>(i) < count; i++) {
        QString key = QStringLiteral("MRU%1").arg(i);
        param->RemoveASCII(key.toStdString().c_str());
    }

    // Add the current values
    int size = _recents.size();
    if (size > _recentMax) {
        size = _recentMax;
    }
    param->SetInt("Recent", size);
    int j = 0;
    for (auto& recent : _recents) {
        QString key = QStringLiteral("MRU%1").arg(j);
        param->SetASCII(key.toStdString().c_str(), recent.toStdString());

        j++;
        if (j >= size) {
            break;
        }
    }
}

void MaterialsEditor::addRecent(const QString& uuid)
{
    // Ensure it is a material. New, unsaved materials will not be
    try {
        auto material = Materials::MaterialManager::getManager().getMaterial(uuid);
        Q_UNUSED(material)
    }
    catch (const Materials::MaterialNotFound&) {
        return;
    }

    // Ensure no duplicates
    if (isRecent(uuid)) {
        _recents.remove(uuid);
    }

    _recents.push_front(uuid);
    while (_recents.size() > static_cast<std::size_t>(_recentMax)) {
        _recents.pop_back();
    }

    saveRecents();
}

bool MaterialsEditor::isRecent(const QString& uuid) const
{
    for (auto& it : _recents) {
        if (it == uuid) {
            return true;
        }
    }
    return false;
}

void MaterialsEditor::onName(const QString& text)
{
    _material->setName(text);
}

void MaterialsEditor::onEditorNameChanged(const QString& newName)
{
    if (m_currentItem && m_currentItem->data(Qt::UserRole + 1).isValid()) {
        QVariant v = m_currentItem->data(Qt::UserRole + 1);
        // If not saved, reflect change in the tree item
        if (v.value<MaterialsEditor::MaterialStatus>() != MaterialsEditor::MaterialStatus::Saved) {
            m_currentItem->setText(newName + "*");
            onDataChanged();
        }
    }
}

void MaterialsEditor::onDataChanged()
{
    if (!m_currentItem) {
        return;
    }

    auto statusVariant = m_currentItem->data(Qt::UserRole + 1);
    if (!statusVariant.isValid()) return;

    if (statusVariant.value<MaterialsEditor::MaterialStatus>() == MaterialsEditor::MaterialStatus::Saved) {
        // Transition the state from Saved to Modified.
        m_currentItem->setData(QVariant::fromValue(MaterialsEditor::MaterialStatus::Modified), Qt::UserRole + 1);

        // Update UI to indicate "unsaved" state.
        m_currentItem->setText(m_currentItem->text() + "*");
        QFont font = m_currentItem->font();
        font.setItalic(true);
        m_currentItem->setFont(font);
    }
}

void MaterialsEditor::onAuthor(const QString& text)
{
    _material->setAuthor(text);
}

void MaterialsEditor::onLicense(const QString& text)
{
    _material->setLicense(text);
}

void MaterialsEditor::onSourceURL(const QString& text)
{
    _material->setURL(text);
}

void MaterialsEditor::onSourceReference(const QString& text)
{
    _material->setReference(text);
}

void MaterialsEditor::onDescription()
{
    _material->setDescription(ui->editDescription->toPlainText());
}

void MaterialsEditor::propertyChange(const QString& property, const QVariant& value)
{
    if (_material->hasPhysicalProperty(property)) {
        _material->setPhysicalValue(property, value);
    }
    else if (_material->hasAppearanceProperty(property)) {
        _material->setAppearanceValue(property, value);
        updatePreview();
    }
    update();
}

void MaterialsEditor::onURL(bool checked)
{
    Q_UNUSED(checked)

    QString url = ui->editSourceURL->text();
    if (url.length() > 0) {
        QDesktopServices::openUrl(QUrl(url, QUrl::TolerantMode));
    }
}

void MaterialsEditor::onPhysicalAdd(bool checked)
{
    Q_UNUSED(checked)

    ModelSelect dialog(this, Materials::ModelFilter_Physical);
    dialog.setModal(true);
    if (dialog.exec() == QDialog::Accepted) {
        QString selected = dialog.selectedModel();
        _material->addPhysical(selected);
        updateMaterial();
    }
    else {
        Base::Console().log("No model selected\n");
    }
}

void MaterialsEditor::onPhysicalRemove(bool checked)
{
    Q_UNUSED(checked)

    QItemSelectionModel* selectionModel = ui->treePhysicalProperties->selectionModel();
    if (selectionModel->hasSelection()) {
        auto index = selectionModel->currentIndex().siblingAtColumn(0);

        auto treeModel = dynamic_cast<const QStandardItemModel*>(index.model());

        // Check we're the material model root.
        auto item = treeModel->itemFromIndex(index);
        auto group = item->parent();
        if (!group) {
            QString propertyName = index.data().toString();

            QString uuid = _material->getModelByName(propertyName);
            _material->removePhysical(uuid);
            updateMaterial();
        }
    }
}

void MaterialsEditor::onAppearanceAdd(bool checked)
{
    Q_UNUSED(checked)

    ModelSelect dialog(this, Materials::ModelFilter_Appearance);
    dialog.setModal(true);
    if (dialog.exec() == QDialog::Accepted) {
        QString selected = dialog.selectedModel();
        _material->addAppearance(selected);
        auto model = Materials::ModelManager::getManager().getModel(selected);
        if (selected == Materials::ModelUUIDs::ModelUUID_Rendering_Basic
            || model->inherits(Materials::ModelUUIDs::ModelUUID_Rendering_Basic)) {
            // Add default appearance properties
            *_material = *(getMaterialManager().defaultAppearance());
        }

        updateMaterial();
    }
    else {
        Base::Console().log("No model selected\n");
    }
}

void MaterialsEditor::onAppearanceRemove(bool checked)
{
    Q_UNUSED(checked)

    QItemSelectionModel* selectionModel = ui->treeAppearance->selectionModel();
    if (selectionModel->hasSelection()) {
        auto index = selectionModel->currentIndex().siblingAtColumn(0);

        auto treeModel = dynamic_cast<const QStandardItemModel*>(index.model());

        // Check we're the material model root.
        auto item = treeModel->itemFromIndex(index);
        auto group = item->parent();
        if (!group) {
            QString propertyName = index.data().toString();

            QString uuid = _material->getModelByName(propertyName);
            _material->removeAppearance(uuid);
            updateMaterial();
        }
    }
}

void MaterialsEditor::onFavourite(bool checked)
{
    Q_UNUSED(checked)

    auto selected = _material->getUUID();
    if (isFavorite(selected)) {
        removeFavorite(selected);
    }
    else {
        addFavorite(selected);
    }
}

void MaterialsEditor::setMaterialDefaults()
{
    _material->setName(tr("Unnamed"));
    std::string Author = App::GetApplication()
                             .GetParameterGroupByPath("User parameter:BaseApp/Preferences/Document")
                             ->GetASCII("prefAuthor", "");
    _material->setAuthor(QString::fromStdString(Author));

    // license stuff
    auto paramGrp {App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Document")};
    auto index = static_cast<int>(paramGrp->GetInt("prefLicenseType", 0));
    const char* name = App::licenseItems.at(index).at(App::posnOfFullName);
    // const char* url = App::licenseItems.at(index).at(App::posnOfUrl);
    // std::string licenseUrl = (paramGrp->GetASCII("prefLicenseUrl", url));
    _material->setLicense(QLatin1String(name));

    // Empty materials will have no parent
    Materials::MaterialManager::getManager().dereference(_material);

    updateMaterial();
    _material->resetEditState();
}

void MaterialsEditor::onNewMaterial(bool checked)
{
    Q_UNUSED(checked)
    if (!checkUnsavedChanges()) {
        return; // User cancelled the action.
    }

    if (!findWritableLibraryNode()) {
        QMessageBox::warning(this, tr("No Writable Library"), tr("A writable material library is required to create new materials."));
        return;
    }

    createTransientItem();
}

void MaterialsEditor::onInheritNewMaterial(bool checked)
{
    Q_UNUSED(checked)
    if (!checkUnsavedChanges()) {
        return; // User cancelled.
    }

    if (!findWritableLibraryNode()) {
        QMessageBox::warning(this, tr("No Writable Library"), tr("A writable material library is required to create new materials."));
        return;
    }

    createTransientItem(true); // true = from inheritance
}

void MaterialsEditor::onOk(bool checked)
{
    Q_UNUSED(checked)
    accept();
}

// onCancel was removed; Cancel is handled by reject() directly.

void MaterialsEditor::onSave(bool checked)
{
    Q_UNUSED(checked)

    saveMaterial();
}

void MaterialsEditor::saveMaterial()
{
    MaterialSave dialog(_material, this);
    dialog.setModal(true);
    if (dialog.exec() == QDialog::Accepted) {
        // The dialog may return a material instance representing the saved object.
        try {
            _material = dialog.getMaterial();
        } catch (...) {
            // If getMaterial is not present or fails, keep current _material.
        }

        // Refresh the tree and re-select the saved item.
        refreshMaterialTree();

        // Try to find the saved material in the refreshed tree and select it.
        QString savedUUID = _material->getUUID();
        QModelIndex newIndex = findInTree(savedUUID);
        if (newIndex.isValid()) {
            auto model = static_cast<QStandardItemModel*>(ui->treeMaterials->model());
            m_currentItem = model->itemFromIndex(newIndex);
            finalizeSavedItem(m_currentItem);
            ui->treeMaterials->selectionModel()->setCurrentIndex(newIndex, QItemSelectionModel::ClearAndSelect);
        } else {
            m_currentItem = nullptr;
        }

        _material->resetEditState();
        _materialSelected = true;
        return true;
    }
    return false;
}

void MaterialsEditor::accept()
{
    if (!checkUnsavedChanges()) {
        return; // User cancelled, so do not close the dialog.
    }
    if (_material && !_material->getUUID().isEmpty()) {
        addRecent(_material->getUUID());
    }
    saveWindow();
    QDialog::accept();
}

void MaterialsEditor::oldFormatError()
{
    QMessageBox box(this);
    box.setIcon(QMessageBox::Warning);
    box.setWindowTitle(tr("Old Format Material"));

    box.setText(tr("This file is in the old material card format."));
    box.setInformativeText(QObject::tr("Save the material before using it."));
    box.adjustSize();  // Silence warnings from Qt on Windows
    box.exec();
}

void MaterialsEditor::reject()
{
    if (!checkUnsavedChanges()) {
        return; // User cancelled, so do not close the dialog.
    }
    saveWindow();
    QDialog::reject();
}

void MaterialsEditor::saveWindow()
{
    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Editor");
    param->SetInt("EditorWidth", width());
    param->SetInt("EditorHeight", height());

    saveMaterialTree(param);
}

void MaterialsEditor::saveMaterialTreeChildren(const Base::Reference<ParameterGrp>& param,
                                               QTreeView* tree,
                                               QStandardItemModel* model,
                                               QStandardItem* item)
{
    if (item->hasChildren()) {
        param->SetBool(item->text().toStdString().c_str(), tree->isExpanded(item->index()));

        auto treeParam = param->GetGroup(item->text().toStdString().c_str());
        for (int i = 0; i < item->rowCount(); i++) {
            auto child = item->child(i);

            saveMaterialTreeChildren(treeParam, tree, model, child);
        }
    }
}

void MaterialsEditor::saveMaterialTree(const Base::Reference<ParameterGrp>& param)
{
    auto treeParam = param->GetGroup("MaterialTree");
    treeParam->Clear();

    auto tree = ui->treeMaterials;
    auto model = qobject_cast<QStandardItemModel*>(tree->model());

    auto root = model->invisibleRootItem();
    for (int i = 0; i < root->rowCount(); i++) {
        auto child = root->child(i);
        // treeParam->SetBool(child->text().toStdString().c_str(),
        // tree->isExpanded(child->index()));

        saveMaterialTreeChildren(treeParam, tree, model, child);
    }
}

void MaterialsEditor::addMaterials(
    QStandardItem& parent,
    const std::shared_ptr<std::map<QString, std::shared_ptr<Materials::MaterialTreeNode>>>
        materialTree,
    const QIcon& folderIcon,
    const QIcon& icon,
    const Base::Reference<ParameterGrp>& param)
{
    auto childParam = param->GetGroup(parent.text().toStdString().c_str());
    auto tree = ui->treeMaterials;
    for (auto& mat : *materialTree) {
        std::shared_ptr<Materials::MaterialTreeNode> nodePtr = mat.second;
        if (nodePtr->getType() == Materials::MaterialTreeNode::NodeType::DataNode) {
            QString uuid = nodePtr->getUUID();
            auto material = nodePtr->getData();
            if (!material) {
                material = Materials::MaterialManager::getManager().getMaterial(uuid);
                nodePtr->setData(material);
            }

            QIcon matIcon = icon;
            if (material->isOldFormat()) {
                matIcon = _warningIcon;
            }
            auto card = new QStandardItem(matIcon, mat.first);
            card->setFlags(Qt::ItemIsSelectable | Qt::ItemIsEnabled | Qt::ItemIsDragEnabled
                           | Qt::ItemIsDropEnabled);
            card->setData(QVariant(uuid), Qt::UserRole);
            // Track the saved state for this item
            card->setData(QVariant::fromValue(MaterialsEditor::MaterialStatus::Saved), Qt::UserRole + 1);
            // Store the material pointer for quick access
            QVariant matVar;
            matVar.setValue(material);
            card->setData(matVar, Qt::UserRole + 2);
            if (material->isOldFormat()) {
                card->setToolTip(tr("This card uses the old format and must be saved before use"));
            }

            addExpanded(tree, &parent, card);
        }
        else {
            auto node = new QStandardItem(folderIcon, mat.first);
            addExpanded(tree, &parent, node, childParam);
            node->setFlags(Qt::ItemIsEnabled | Qt::ItemIsDragEnabled | Qt::ItemIsDropEnabled);
            auto treeMap = nodePtr->getFolder();
            // if (treeMap) {
                addMaterials(*node, treeMap, folderIcon, icon, childParam);
            // }
        }
    }
}

void MaterialsEditor::addExpanded(QTreeView* tree, QStandardItem* parent, QStandardItem* child)
{
    parent->appendRow(child);
    tree->setExpanded(child->index(), true);
}

void MaterialsEditor::addExpanded(QTreeView* tree,
                                  QStandardItem* parent,
                                  QStandardItem* child,
                                  const Base::Reference<ParameterGrp>& param)
{
    parent->appendRow(child);

    // Restore to any previous expansion state
    auto expand = param->GetBool(child->text().toStdString().c_str(), true);
    tree->setExpanded(child->index(), expand);
}

void MaterialsEditor::addExpanded(QTreeView* tree, QStandardItemModel* parent, QStandardItem* child)
{
    parent->appendRow(child);
    tree->setExpanded(child->index(), true);
}

void MaterialsEditor::addExpanded(QTreeView* tree,
                                  QStandardItemModel* parent,
                                  QStandardItem* child,
                                  const Base::Reference<ParameterGrp>& param)
{
    parent->appendRow(child);

    // Restore to any previous expansion state
    auto expand = param->GetBool(child->text().toStdString().c_str(), true);
    tree->setExpanded(child->index(), expand);
}

void MaterialsEditor::createPhysicalTree()
{
    auto tree = ui->treePhysicalProperties;
    auto model = new QStandardItemModel();
    tree->setModel(model);

    QStringList headers;
    headers.append(tr("Property"));
    headers.append(tr("Value"));
    headers.append(tr("Type"));
    model->setHorizontalHeaderLabels(headers);

    tree->setColumnWidth(0, 250);
    tree->setColumnWidth(1, 250);
    tree->setColumnHidden(2, true);

    tree->setHeaderHidden(false);
    tree->setUniformRowHeights(false);
    auto delegate = new MaterialDelegate(this);
    tree->setItemDelegateForColumn(1, delegate);

    connect(delegate, &MaterialDelegate::propertyChange, this, &MaterialsEditor::propertyChange);
}

void MaterialsEditor::createPreviews()
{
    _rendered = new AppearancePreview();
    ui->layoutAppearance->addWidget(_rendered);

    updatePreview();
}

void MaterialsEditor::createAppearanceTree()
{
    auto tree = ui->treeAppearance;
    auto model = new QStandardItemModel();
    tree->setModel(model);

    QStringList headers;
    headers.append(tr("Property"));
    headers.append(tr("Value"));
    headers.append(tr("Type"));
    model->setHorizontalHeaderLabels(headers);

    tree->setColumnWidth(0, 250);
    tree->setColumnWidth(1, 250);
    tree->setColumnHidden(2, true);

    tree->setHeaderHidden(false);
    tree->setUniformRowHeights(false);
    auto delegate = new MaterialDelegate(this);
    tree->setItemDelegateForColumn(1, delegate);

    connect(delegate, &MaterialDelegate::propertyChange, this, &MaterialsEditor::propertyChange);
}

QIcon MaterialsEditor::getIcon(const std::shared_ptr<Materials::Library>& library)
{
    // Load from the QByteArray if available
    QIcon icon;
    if (library->hasIcon()) {
        QImage image;
        if (!image.loadFromData(library->getIcon())) {
            Base::Console().log("Unable to load icon image for library '%s'\n",
                                library->getName().toStdString().c_str());
            return QIcon();
        }
        icon = QIcon(QPixmap::fromImage(image));
    }

    return icon;
}

QIcon MaterialsEditor::getIcon(const std::shared_ptr<Materials::ModelLibrary>& library)
{
    return getIcon(std::static_pointer_cast<Materials::Library>(library));
}

QIcon MaterialsEditor::getIcon(const std::shared_ptr<Materials::MaterialLibrary>& library)
{
    return getIcon(std::static_pointer_cast<Materials::Library>(library));
}

void MaterialsEditor::addRecents(QStandardItem* parent)
{
    auto tree = ui->treeMaterials;
    for (auto& uuid : _recents) {
        try {
            auto material = getMaterialManager().getMaterial(uuid);
            // if (material->getLibrary()->isLocal()) {
            QIcon icon = getIcon(material->getLibrary());
            auto card = new QStandardItem(icon, libraryPath(material));
            card->setFlags(Qt::ItemIsSelectable | Qt::ItemIsEnabled | Qt::ItemIsDragEnabled
                           | Qt::ItemIsDropEnabled);
            card->setData(QVariant(uuid), Qt::UserRole);

            addExpanded(tree, parent, card);
            // }
        }
        catch (const Materials::MaterialNotFound&) {
        }
    }
}

void MaterialsEditor::addFavorites(QStandardItem* parent)
{
    auto tree = ui->treeMaterials;
    for (auto& uuid : _favorites) {
        try {
            auto material = getMaterialManager().getMaterial(uuid);
            QIcon icon = getIcon(material->getLibrary());
            auto card = new QStandardItem(icon, libraryPath(material));
            card->setFlags(Qt::ItemIsSelectable | Qt::ItemIsEnabled | Qt::ItemIsDragEnabled
                            | Qt::ItemIsDropEnabled);
            card->setData(QVariant(uuid), Qt::UserRole);

            addExpanded(tree, parent, card);
        }
        catch (const Materials::MaterialNotFound&) {
        }
    }
}

void MaterialsEditor::fillMaterialTree()
{
    auto param = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Material/Editor/MaterialTree");

    auto tree = ui->treeMaterials;
    auto model = qobject_cast<QStandardItemModel*>(tree->model());

    if (_filterOptions.includeFavorites()) {
        auto lib = new QStandardItem(tr("Favorites"));
        lib->setFlags(Qt::ItemIsEnabled | Qt::ItemIsDragEnabled | Qt::ItemIsDropEnabled);
        addExpanded(tree, model, lib, param);
        addFavorites(lib);
    }

    if (_filterOptions.includeRecent()) {
        auto lib = new QStandardItem(tr("Recent"));
        lib->setFlags(Qt::ItemIsEnabled | Qt::ItemIsDragEnabled | Qt::ItemIsDropEnabled);
        addExpanded(tree, model, lib, param);
        addRecents(lib);
    }

    auto libraries = getMaterialManager().getLibraries();
    for (const auto& library : *libraries) {
        auto materialTree = getMaterialManager().getMaterialTree(*library);

        bool showLibraries = _filterOptions.includeEmptyLibraries();
        if (!_filterOptions.includeEmptyLibraries() && materialTree->size() > 0) {
            showLibraries = true;
        }

        if (showLibraries) {
            auto lib = new QStandardItem(library->getName());
            lib->setFlags(Qt::ItemIsEnabled | Qt::ItemIsDragEnabled | Qt::ItemIsDropEnabled);
            // mark library read-only state for writable library discovery
            lib->setData(QVariant(library->isReadOnly()), Qt::UserRole + 3);
            addExpanded(tree, model, lib, param);

            QIcon icon = getIcon(library);
            QIcon folderIcon(QStringLiteral(":/icons/folder.svg"));

            addMaterials(*lib, materialTree, folderIcon, icon, param);
        }
    }
}

void MaterialsEditor::createMaterialTree()
{
    auto tree = ui->treeMaterials;
    auto model = new QStandardItemModel();
    tree->setModel(model);

    tree->setHeaderHidden(true);
    fillMaterialTree();
}

void MaterialsEditor::refreshMaterialTree()
{
    auto tree = ui->treeMaterials;
    auto model = qobject_cast<QStandardItemModel*>(tree->model());
    model->clear();

    fillMaterialTree();
}

bool MaterialsEditor::updateTexturePreview() const
{
    bool hasImage = false;
    QImage image;
    // double scaling = 99.0;
    if (_material->hasModel(Materials::ModelUUIDs::ModelUUID_Rendering_Texture)) {
        // First try loading an embedded image
        try {
            auto property = _material->getAppearanceProperty(QStringLiteral("TextureImage"));
            if (!property->isNull()) {
                auto propertyValue = property->getString();
                if (!propertyValue.isEmpty()) {
                    QByteArray by = QByteArray::fromBase64(propertyValue.toUtf8());
                    image = QImage::fromData(by);
                    hasImage = !image.isNull();
                }
            }
        }
        catch (const Materials::PropertyNotFound&) {
        }

        // If no embedded image, load from a path
        if (!hasImage) {
            try {
                auto property = _material->getAppearanceProperty(QStringLiteral("TexturePath"));
                if (!property->isNull()) {
                    // Base::Console().log("Has 'TexturePath'\n");
                    auto filePath = property->getString();
                    if (!image.load(filePath)) {
                        Base::Console().log("Unable to load image '%s'\n",
                                            filePath.toStdString().c_str());
                        hasImage = false;
                    }
                    else {
                        hasImage = !image.isNull();
                    }
                }
            }
            catch (const Materials::PropertyNotFound&) {
            }
        }

        // Apply any scaling
        try {
            auto property = _material->getAppearanceProperty(QStringLiteral("TextureScaling"));
            if (!property->isNull()) {
                // scaling = property->getFloat();
                //  Base::Console().log("Has 'TextureScaling' = %g\n", scaling);
            }
        }
        catch (const Materials::PropertyNotFound&) {
        }

        if (hasImage) {
            _rendered->setTexture(image);
        }
    }

    return hasImage;
}

bool MaterialsEditor::updateMaterialPreview() const
{
    if (_material->hasAppearanceProperty(QStringLiteral("AmbientColor"))) {
        QString color = _material->getAppearanceValueString(QStringLiteral("AmbientColor"));
        _rendered->setAmbientColor(getColorHash(color, 255));
    }
    else {
        _rendered->resetAmbientColor();
    }
    if (_material->hasAppearanceProperty(QStringLiteral("DiffuseColor"))) {
        QString color = _material->getAppearanceValueString(QStringLiteral("DiffuseColor"));
        _rendered->setDiffuseColor(getColorHash(color, 255));
    }
    else {
        _rendered->resetDiffuseColor();
    }
    if (_material->hasAppearanceProperty(QStringLiteral("SpecularColor"))) {
        QString color = _material->getAppearanceValueString(QStringLiteral("SpecularColor"));
        _rendered->setSpecularColor(getColorHash(color, 255));
    }
    else {
        _rendered->resetSpecularColor();
    }
    if (_material->hasAppearanceProperty(QStringLiteral("EmissiveColor"))) {
        QString color = _material->getAppearanceValueString(QStringLiteral("EmissiveColor"));
        _rendered->setEmissiveColor(getColorHash(color, 255));
    }
    else {
        _rendered->resetEmissiveColor();
    }
    if (_material->hasAppearanceProperty(QStringLiteral("Shininess"))) {
        double value = _material->getAppearanceValue(QStringLiteral("Shininess")).toDouble();
        _rendered->setShininess(value);
    }
    else {
        _rendered->resetShininess();
    }
    if (_material->hasAppearanceProperty(QStringLiteral("Transparency"))) {
        double value = _material->getAppearanceValue(QStringLiteral("Transparency")).toDouble();
        _rendered->setTransparency(value);
    }
    else {
        _rendered->resetTransparency();
    }

    return true;
}

void MaterialsEditor::updatePreview() const
{
    if (updateTexturePreview()) {
        return;
    }
    updateMaterialPreview();
}

QString MaterialsEditor::getColorHash(const QString& colorString, int colorRange)
{
    /*
        returns a '#000000' string from a '(0.1,0.2,0.3)' string. Optionally the string
        has a fourth value for alpha (transparency)
    */
    std::stringstream stream(colorString.toStdString());

    char c;
    stream >> c;  // read "("
    double red;
    stream >> red;
    stream >> c;  // ","
    double green;
    stream >> green;
    stream >> c;  // ","
    double blue;
    stream >> blue;
    stream >> c;  // ","
    double alpha = 1.0;
    if (c == ',') {
        stream >> alpha;
    }

    QColor color(static_cast<int>(red * colorRange),
                 static_cast<int>(green * colorRange),
                 static_cast<int>(blue * colorRange),
                 static_cast<int>(alpha * colorRange));
    return color.name();
}

void MaterialsEditor::updateMaterialAppearance()
{
    QTreeView* tree = ui->treeAppearance;
    auto treeModel = qobject_cast<QStandardItemModel*>(tree->model());
    treeModel->clear();

    QStringList headers;
    headers.append(tr("Property"));
    headers.append(tr("Value"));
    headers.append(tr("Type"));
    treeModel->setHorizontalHeaderLabels(headers);

    tree->setColumnWidth(0, 250);
    tree->setColumnWidth(1, 250);
    tree->setColumnHidden(2, true);

    auto models = _material->getAppearanceModels();
    if (models) {
        for (auto it = models->begin(); it != models->end(); it++) {
            QString uuid = *it;
            try {
                auto model = Materials::ModelManager::getManager().getModel(uuid);
                QString name = model->getName();

                auto modelRoot = new QStandardItem(name);
                modelRoot->setFlags(Qt::ItemIsEnabled | Qt::ItemIsDragEnabled
                                    | Qt::ItemIsDropEnabled);
                addExpanded(tree, treeModel, modelRoot);
                for (auto itp = model->begin(); itp != model->end(); itp++) {
                    QList<QStandardItem*> items;

                    QString key = itp->first;
                    // auto propertyItem = new QStandardItem(key);
                    auto propertyItem = new QStandardItem(itp->second.getDisplayName());
                    propertyItem->setData(key);
                    propertyItem->setToolTip(itp->second.getDescription());
                    items.append(propertyItem);

                    auto valueItem = new QStandardItem(_material->getAppearanceValueString(key));
                    valueItem->setToolTip(itp->second.getDescription());
                    QVariant variant;
                    // variant.setValue(_material->getAppearanceValueString(key));
                    variant.setValue(_material);
                    valueItem->setData(variant);
                    items.append(valueItem);

                    auto typeItem = new QStandardItem(itp->second.getPropertyType());
                    items.append(typeItem);

                    auto unitsItem = new QStandardItem(itp->second.getUnits());
                    items.append(unitsItem);

                    modelRoot->appendRow(items);
                    tree->setExpanded(modelRoot->index(), true);
                }
            }
            catch (Materials::ModelNotFound const&) {
            }
        }
    }
}

void MaterialsEditor::updateMaterialProperties()
{
    QTreeView* tree = ui->treePhysicalProperties;
    auto treeModel = qobject_cast<QStandardItemModel*>(tree->model());
    treeModel->clear();

    QStringList headers;
    headers.append(tr("Property"));
    headers.append(tr("Value"));
    headers.append(tr("Type"));
    headers.append(tr("Units"));
    treeModel->setHorizontalHeaderLabels(headers);

    tree->setColumnWidth(0, 250);
    tree->setColumnWidth(1, 250);
    tree->setColumnHidden(2, true);
    tree->setColumnHidden(3, true);

    auto models = _material->getPhysicalModels();
    if (models) {
        for (auto it = models->begin(); it != models->end(); it++) {
            QString uuid = *it;
            try {
                auto model = Materials::ModelManager::getManager().getModel(uuid);
                QString name = model->getName();

                auto modelRoot = new QStandardItem(name);
                modelRoot->setFlags(Qt::ItemIsEnabled | Qt::ItemIsDragEnabled
                                    | Qt::ItemIsDropEnabled);
                addExpanded(tree, treeModel, modelRoot);
                for (auto itp = model->begin(); itp != model->end(); itp++) {
                    QList<QStandardItem*> items;

                    QString key = itp->first;
                    Materials::ModelProperty modelProperty =
                        static_cast<Materials::ModelProperty>(itp->second);
                    // auto propertyItem = new QStandardItem(key);
                    auto propertyItem = new QStandardItem(modelProperty.getDisplayName());
                    propertyItem->setData(key);
                    propertyItem->setToolTip(modelProperty.getDescription());
                    items.append(propertyItem);

                    auto valueItem = new QStandardItem(_material->getPhysicalValueString(key));
                    valueItem->setToolTip(modelProperty.getDescription());
                    QVariant variant;
                    variant.setValue(_material);
                    valueItem->setData(variant);
                    items.append(valueItem);

                    auto typeItem = new QStandardItem(modelProperty.getPropertyType());
                    items.append(typeItem);

                    auto unitsItem = new QStandardItem(modelProperty.getUnits());
                    items.append(unitsItem);

                    // addExpanded(tree, modelRoot, propertyItem);
                    modelRoot->appendRow(items);
                    tree->setExpanded(modelRoot->index(), true);
                }
            }
            catch (Materials::ModelNotFound const&) {
            }
        }
    }
}

QString MaterialsEditor::libraryPath(const std::shared_ptr<Materials::Material>& material)
{
    QString path;
    auto library = material->getLibrary();
    if (library) {
        path = QStringLiteral("/%1/%2/%3")
                   .arg(library->getName())
                   .arg(material->getDirectory())
                   .arg(material->getName());
        return path;
    }

    path = QStringLiteral("%1/%2").arg(material->getDirectory()).arg(material->getName());
    return path;
}

void MaterialsEditor::updateMaterialGeneral()
{
    QString parentString;
    try {
        auto parent = Materials::MaterialManager::getManager().getParent(_material);
        parentString = libraryPath(parent);
    }
    catch (const Materials::MaterialNotFound&) {
    }

    // Update the general information
    ui->editName->setText(_material->getName());
    ui->editAuthor->setText(_material->getAuthor());
    ui->editLicense->setText(_material->getLicense());
    ui->editParent->setText(parentString);
    ui->editParent->setReadOnly(true);
    ui->editSourceURL->setText(_material->getURL());
    ui->editSourceReference->setText(_material->getReference());
    // ui->editTags->setText(_material->getName());
    ui->editDescription->setText(_material->getDescription());
}

void MaterialsEditor::updateMaterial()
{
    updateMaterialGeneral();
    updateMaterialProperties();
    updateMaterialAppearance();

    updatePreview();
}

void MaterialsEditor::onSelectMaterial(const QItemSelection& selected,
                                       const QItemSelection& deselected)
{
    Q_UNUSED(deselected);
    if (selected.isEmpty() || !selected.indexes().first().isValid()) {
        return;
    }

    // 1. Check for unsaved changes before allowing the selection to change.
    if (!checkUnsavedChanges()) {
        // If the user cancels, revert the selection in the UI.
        QSignalBlocker blocker(ui->treeMaterials->selectionModel());
        if (m_currentItem) {
            ui->treeMaterials->selectionModel()->setCurrentIndex(
                m_currentItem->index(), QItemSelectionModel::ClearAndSelect);
        }
        return;
    }

    // 2. Proceed with loading the newly selected material.
    auto model = qobject_cast<QStandardItemModel*>(ui->treeMaterials->model());
    auto* selectedItem = model->itemFromIndex(selected.indexes().first());

    if (!selectedItem || selectedItem == m_currentItem) {
        return; // No real change.
    }

    m_currentItem = selectedItem;
    QString uuid = m_currentItem->data(Qt::UserRole).toString();

    if (uuid.isEmpty()) { // It's a folder or library node.
        _material = std::make_shared<Materials::Material>();
        setMaterialDefaults(); // Clear the editor panel.
        return;
    }

    // Get the selected material
    try {
        _material = std::make_shared<Materials::Material>(*getMaterialManager().getMaterial(uuid));
    } catch (const Materials::ModelNotFound&) {
        Base::Console().log("*** Unable to load material '%s'\n", uuid.toStdString().c_str());
        _material = std::make_shared<Materials::Material>();
    }

    updateMaterial();
    _materialSelected = true;

    // After loading, the state is 'Saved' by definition.
    m_currentItem->setData(QVariant::fromValue(MaterialsEditor::MaterialStatus::Saved), Qt::UserRole + 1);
}

void MaterialsEditor::onDoubleClick(const QModelIndex& index)
{
    Q_UNUSED(index)
    // Trigger the accept action, which will handle unsaved changes.
    accept();
}

void MaterialsEditor::onContextMenu(const QPoint& pos)
{
    QMenu contextMenu(tr("Context Menu"), this);

    QAction action1(tr("Inherit From"), this);
    connect(&action1, &QAction::triggered, this, &MaterialsEditor::onInherit);
    contextMenu.addAction(&action1);

    QAction action2(tr("Inherit New Material"), this);
    connect(&action2, &QAction::triggered, this, &MaterialsEditor::onInheritNew);
    contextMenu.addAction(&action2);

    contextMenu.exec(ui->treeMaterials->mapToGlobal(pos));
}

void MaterialsEditor::onInherit(bool checked)
{
    Q_UNUSED(checked)
}

void MaterialsEditor::onInheritNew(bool checked)
{
    Q_UNUSED(checked)
}
// Helper: find the QModelIndex for a material UUID in the materials tree.
QModelIndex MaterialsEditor::findInTree(const QString& uuid)
{
    auto* model = static_cast<QStandardItemModel*>(ui->treeMaterials->model());
    if (!model) return QModelIndex();

    QStandardItem* root = model->invisibleRootItem();
    std::function<QModelIndex(QStandardItem*)> search = [&](QStandardItem* item) -> QModelIndex {
        if (!item) return QModelIndex();
        QVariant v = item->data(Qt::UserRole);
        if (v.isValid() && v.toString() == uuid) {
            return item->index();
        }
        for (int i = 0; i < item->rowCount(); ++i) {
            QModelIndex found = search(item->child(i));
            if (found.isValid()) return found;
        }
        return QModelIndex();
    };

    for (int i = 0; i < root->rowCount(); ++i) {
        QModelIndex idx = search(root->child(i));
        if (idx.isValid()) return idx;
    }
    return QModelIndex();
}

bool MaterialsEditor::checkUnsavedChanges()
{
    if (!m_currentItem) {
        return true; // No item selected, nothing to save.
    }

    auto statusVariant = m_currentItem->data(Qt::UserRole + 1);
    if (!statusVariant.isValid() || statusVariant.value<MaterialsEditor::MaterialStatus>() == MaterialsEditor::MaterialStatus::Saved) {
        return true; // Not a material item or no changes to save.
    }

    QMessageBox box(this);
    box.setIcon(QMessageBox::Question);
    box.setText(tr("The current material has been modified."));
    box.setInformativeText(tr("Do you want to save your changes?"));
    box.setStandardButtons(QMessageBox::Save | QMessageBox::Discard | QMessageBox::Cancel);
    box.setDefaultButton(QMessageBox::Save);

    int ret = box.exec();

    switch (ret) {
    case QMessageBox::Save:
        return saveMaterial(); // Proceed only if save was successful.
    case QMessageBox::Discard:
        if (statusVariant.value<MaterialsEditor::MaterialStatus>() == MaterialsEditor::MaterialStatus::New_Unsaved) {
            // If the unsaved item was new, remove it from the tree.
            if (m_currentItem->parent()) {
                m_currentItem->parent()->removeRow(m_currentItem->row());
            } else {
                qobject_cast<QStandardItemModel*>(ui->treeMaterials->model())->removeRow(m_currentItem->row());
            }
            m_currentItem = nullptr;
        } else if (statusVariant.value<MaterialsEditor::MaterialStatus>() == MaterialsEditor::MaterialStatus::Modified) {
            revertModifiedItem(m_currentItem);
        }
        return true;
    case QMessageBox::Cancel:
    default:
        return false; // User cancelled the parent action.
    }
}

void MaterialsEditor::createTransientItem(bool fromInheritance)
{
    auto parentUUID = _material ? _material->getUUID() : QString();

    _material = std::make_shared<Materials::Material>();
    if (fromInheritance && !parentUUID.isEmpty()) {
        _material->setParentUUID(parentUUID);
    }
    setMaterialDefaults();

    auto* model = static_cast<QStandardItemModel*>(ui->treeMaterials->model());
    QStandardItem* newItem = new QStandardItem(tr("New Material*"));

    QFont font;
    font.setItalic(true);
    newItem->setFont(font);
    
    newItem->setData(QVariant::fromValue(MaterialsEditor::MaterialStatus::New_Unsaved), Qt::UserRole + 1);
    QVariant matVar;
    matVar.setValue(_material);
    newItem->setData(matVar, Qt::UserRole + 2);

    QStandardItem* parentNode = findWritableLibraryNode();
    if (parentNode) {
        parentNode->appendRow(newItem);
        ui->treeMaterials->expand(parentNode->index());
    } else {
        model->invisibleRootItem()->appendRow(newItem);
    }
    
    ui->treeMaterials->selectionModel()->setCurrentIndex(newItem->index(), QItemSelectionModel::ClearAndSelect);
    ui->editName->setFocus();
    ui->editName->selectAll();
    
    m_currentItem = newItem;
    updateMaterial(); // Load blank data into editor
}

void MaterialsEditor::finalizeSavedItem(QStandardItem* item)
{
    if (!item) return;
    item->setText(_material->getName());
    QFont font;
    font.setItalic(false);
    item->setFont(font);

    item->setData(QVariant::fromValue(MaterialsEditor::MaterialStatus::Saved), Qt::UserRole + 1);
    QVariant matVar;
    matVar.setValue(_material);
    item->setData(matVar, Qt::UserRole + 2);
}

void MaterialsEditor::revertModifiedItem(QStandardItem* item)
{
    if (!item) return;
    QString uuid = item->data(Qt::UserRole).toString();
    if (uuid.isEmpty()) return;

    try {
        auto cleanMaterial = Materials::MaterialManager::getManager().getMaterial(uuid);
        _material = std::make_shared<Materials::Material>(*cleanMaterial);
    } catch (...) {
        _material = std::make_shared<Materials::Material>();
        setMaterialDefaults();
        return;
    }

    // Revert the tree item's appearance.
    item->setText(_material->getName());
    QFont font = item->font();
    font.setItalic(false);
    item->setFont(font);
    item->setData(QVariant::fromValue(MaterialsEditor::MaterialStatus::Saved), Qt::UserRole + 1);

    // Reload the editor panel with the clean data.
    updateMaterial();
}

QStandardItem* MaterialsEditor::findWritableLibraryNode()
{
    auto* model = static_cast<QStandardItemModel*>(ui->treeMaterials->model());
    QStandardItem* root = model->invisibleRootItem();
    
    for (int i = 0; i < root->rowCount(); ++i) {
        QStandardItem* child = root->child(i);
        auto readOnlyVariant = child->data(Qt::UserRole + 3);
        if (readOnlyVariant.isValid() && !readOnlyVariant.toBool()) {
            return child; // It's a writable library node.
        }
    }
    // Fallback: try to find a node named "User".
    for (int i = 0; i < root->rowCount(); ++i) {
        QStandardItem* child = root->child(i);
        if (child->text().contains("User")) { 
            return child;
        }
    }
    return nullptr; // No writable library found.
}

#include "moc_MaterialsEditor.cpp"
